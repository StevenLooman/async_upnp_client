# -*- coding: utf-8 -*-
"""UPnP event handler module."""

import asyncio
import logging
import urllib.parse
from datetime import datetime, timedelta
from http import HTTPStatus
import socket
from socket import AddressFamily  # pylint: disable=no-name-in-module
from typing import Dict, Mapping, NamedTuple, Optional, Tuple

import defusedxml.ElementTree as DET

from async_upnp_client.client import UpnpError, UpnpRequester, UpnpService
from async_upnp_client.const import NS
from async_upnp_client.utils import async_get_local_ip, get_local_ip

_LOGGER = logging.getLogger(__name__)
_LOGGER_TRAFFIC_UPNP = logging.getLogger("async_upnp_client.traffic.upnp")


SubscriptionInfo = NamedTuple(
    "SubscriptionInfo",
    [("service", UpnpService), ("timeout", timedelta), ("renewal_time", datetime)],
)


class UpnpEventHandler:
    """
    Handles upnp eventing.

    An incoming NOTIFY request should be pass to handle_notify().
    subscribe/resubscribe/unsubscribe handle subscriptions.
    """

    def __init__(
        self,
        callback_url: str,
        requester: UpnpRequester,
        listen_ports: Optional[Mapping[AddressFamily, int]] = None,
    ) -> None:
        """Initialize.

        callback_url can be a normal URL or a format string with {host} and
            {port} placeholders that will be filled based on how the device is
            connected.
        listen_ports is a mapping of IP version to the local listening port,
            used to determine callback_url for devices.
        """
        self._callback_url = callback_url
        self._requester = requester

        self.listen_ports = listen_ports or {}

        self._listen_ip: Optional[str] = None
        self._subscriptions: Dict[str, SubscriptionInfo] = {}
        self._backlog: Dict[str, Tuple[Mapping, str]] = {}

    @property
    def callback_url(self) -> str:
        """Return callback URL on which we are callable.

        This URL should work for most cases, but makes assumptions about how
        a device will connect. Use callback_url_for_service to get a more
        specific URL.
        """
        if not self._listen_ip:
            self._listen_ip = get_local_ip()
        port = self.listen_ports.get(socket.AF_INET)
        if not port and "{port}" in self._callback_url:
            raise ValueError("callback_url format requires a listening port")
        return self._callback_url.format(host=self._listen_ip, port=port)

    async def async_callback_url_for_service(self, service: UpnpService) -> str:
        """Determine a URL for the service to call back on.

        This can vary based on the service device's IP address.
        """
        _LOGGER.debug("Determine callback URL for: %s", service)

        # Shortcut when callback_url can be determined without connecting to the
        # service device
        if "{host}" not in self._callback_url and (
            len(self.listen_ports) == 1 or "{port}" not in self._callback_url
        ):
            return self.callback_url

        # Figure out how this host connects to the device, then infer how the
        # device can connect back
        device_host = urllib.parse.urlparse(service.device.device_url).netloc
        addr_family, local_host = await async_get_local_ip(device_host)
        port = self.listen_ports[addr_family]

        return self._callback_url.format(host=local_host, port=port)

    def sid_for_service(self, service: UpnpService) -> Optional[str]:
        """Get the service connected to SID."""
        for sid, entry in self._subscriptions.items():
            if entry.service == service:
                return sid

        return None

    def service_for_sid(self, sid: str) -> Optional[UpnpService]:
        """Get a UpnpService for SID."""
        if sid not in self._subscriptions:
            return None

        return self._subscriptions[sid].service

    async def handle_notify(self, headers: Mapping[str, str], body: str) -> HTTPStatus:
        """Handle a NOTIFY request."""
        # ensure valid request
        _LOGGER_TRAFFIC_UPNP.debug(
            "Incoming request:\nNOTIFY\n%s\n\n%s",
            "\n".join([key + ": " + value for key, value in headers.items()]),
            body,
        )
        if "NT" not in headers or "NTS" not in headers:
            _LOGGER_TRAFFIC_UPNP.debug("Sending response: %s", HTTPStatus.BAD_REQUEST)
            return HTTPStatus.BAD_REQUEST

        if (
            headers["NT"] != "upnp:event"
            or headers["NTS"] != "upnp:propchange"
            or "SID" not in headers
        ):
            _LOGGER_TRAFFIC_UPNP.debug(
                "Sending response: %s", HTTPStatus.PRECONDITION_FAILED
            )
            return HTTPStatus.PRECONDITION_FAILED
        sid = headers["SID"]

        # SID not known yet? store it in the backlog
        # Some devices don't behave nicely and send events before the SUBSCRIBE call is done.
        if sid not in self._subscriptions:
            _LOGGER.debug("Storing NOTIFY in backlog for SID: %s", sid)
            self._backlog[sid] = (
                headers,
                body,
            )

            _LOGGER_TRAFFIC_UPNP.debug("Sending response: %s", HTTPStatus.OK)
            return HTTPStatus.OK

        # decode event and send updates to service
        changes = {}
        stripped_body = body.rstrip(" \t\r\n\0")
        el_root = DET.fromstring(stripped_body)
        for el_property in el_root.findall("./event:property", NS):
            for el_state_var in el_property:
                name = el_state_var.tag
                value = el_state_var.text or ""
                changes[name] = value

        # send changes to service
        service = self._subscriptions[sid].service
        service.notify_changed_state_variables(changes)

        _LOGGER_TRAFFIC_UPNP.debug("Sending response: %s", HTTPStatus.OK)
        return HTTPStatus.OK

    async def async_subscribe(
        self,
        service: UpnpService,
        timeout: timedelta = timedelta(seconds=1800),
    ) -> Tuple[bool, Optional[str], Optional[timedelta]]:
        """
        Subscription to a UpnpService.

        Be sure to re-subscribe before the subscription timeout passes.

        :param service UpnpService to subscribe to self
        :param timeout Timeout of subscription
        """
        callback_url = await self.async_callback_url_for_service(service)

        _LOGGER.debug("Subscribing to: %s, callback URL: %s", service, callback_url)

        # do SUBSCRIBE request
        headers = {
            "NT": "upnp:event",
            "TIMEOUT": "Second-" + str(timeout.seconds),
            "HOST": urllib.parse.urlparse(service.event_sub_url).netloc,
            "CALLBACK": "<{}>".format(callback_url),
        }
        response_status, response_headers, _ = await self._requester.async_http_request(
            "SUBSCRIBE", service.event_sub_url, headers
        )

        # check results
        if response_status != 200:
            _LOGGER.debug("Did not receive 200, but %s", response_status)
            return False, None, None

        if "sid" not in response_headers:
            _LOGGER.debug("No SID received, aborting subscribe")
            return False, None, None

        # Device can give a different TIMEOUT header than what we have provided.
        new_timeout = timeout
        if (
            "timeout" in response_headers
            and response_headers["timeout"] != "Second-infinite"
            and "Second-" in response_headers["timeout"]
        ):
            response_timeout = response_headers["timeout"]
            timeout_seconds = int(response_timeout[7:])  # len("Second-") == 7
            new_timeout = timedelta(seconds=timeout_seconds)

        sid = response_headers["sid"]
        renewal_time = datetime.now() + new_timeout
        self._subscriptions[sid] = SubscriptionInfo(
            service=service,
            timeout=timeout,
            renewal_time=renewal_time,
        )
        _LOGGER.debug("Got SID: %s, renewal_time: %s", sid, renewal_time)

        # replay any backlog we have for this service
        if sid in self._backlog:
            _LOGGER.debug("Re-playing backlogged NOTIFY for SID: %s", sid)
            item = self._backlog[sid]
            await self.handle_notify(item[0], item[1])
            del self._backlog[sid]

        return True, sid, new_timeout

    async def async_resubscribe(
        self,
        service: "UpnpService",
        timeout: timedelta = timedelta(seconds=1800),
    ) -> Tuple[bool, Optional[str], Optional[timedelta]]:
        """Renew subscription to a UpnpService."""
        _LOGGER.debug("Resubscribing to: %s", service)

        # do SUBSCRIBE request
        sid = self.sid_for_service(service)
        if not sid:
            raise UpnpError("Could not find SID for service")

        headers = {
            "HOST": urllib.parse.urlparse(service.event_sub_url).netloc,
            "SID": sid,
            "TIMEOUT": "Second-" + str(timeout.total_seconds()),
        }
        response_status, response_headers, _ = await self._requester.async_http_request(
            "SUBSCRIBE", service.event_sub_url, headers
        )

        # check results
        if response_status != 200:
            _LOGGER.debug("Did not receive 200, but %s", response_status)
            return False, None, None

        # Devices should return the SID when re-subscribe,
        # but in case it doesn't, use the new SID.
        if "sid" in response_headers and response_headers["sid"]:
            new_sid: str = response_headers["sid"]
            if new_sid != sid:
                del self._subscriptions[sid]
                sid = new_sid

        # Device can give a different TIMEOUT header than what we have provided.
        new_timeout = timeout
        if (
            "timeout" in response_headers
            and response_headers["timeout"] != "Second-infinite"
            and "Second-" in response_headers["timeout"]
        ):
            response_timeout = response_headers["timeout"]
            timeout_seconds = int(response_timeout[7:])  # len("Second-") == 7
            new_timeout = timedelta(seconds=timeout_seconds)

        renewal_time = datetime.now() + new_timeout
        self._subscriptions[sid] = SubscriptionInfo(
            service=service,
            timeout=timeout,
            renewal_time=renewal_time,
        )
        _LOGGER.debug("Got SID: %s, renewal_time: %s", sid, renewal_time)

        return True, sid, new_timeout

    async def async_resubscribe_all(self) -> None:
        """Renew all current subscription."""
        await asyncio.gather(
            *(self.async_resubscribe(entry.service)
              for entry in self._subscriptions.values())
        )

    async def async_unsubscribe(
        self, service: "UpnpService"
    ) -> Tuple[bool, Optional[str]]:
        """Unsubscribe from a UpnpService."""
        _LOGGER.debug("Unsubscribing from: %s, device: %s", service, service.device)

        # do UNSUBSCRIBE request
        sid = self.sid_for_service(service)
        if not sid:
            _LOGGER.debug("Could not determine SID to unsubscribe")
            return False, None

        headers = {
            "HOST": urllib.parse.urlparse(service.event_sub_url).netloc,
            "SID": sid,
        }
        response_status, _, _ = await self._requester.async_http_request(
            "UNSUBSCRIBE", service.event_sub_url, headers
        )

        # check results
        if response_status != 200:
            _LOGGER.debug("Did not receive 200, but %s", response_status)
            return False, None

        # remove registration
        if sid in self._subscriptions:
            del self._subscriptions[sid]
        return True, sid

    async def async_unsubscribe_all(self) -> None:
        """Unsubscribe all subscriptions."""
        services = self._subscriptions.copy()
        await asyncio.gather(
            *(self.async_unsubscribe(entry.service) for entry in services.values())
        )
