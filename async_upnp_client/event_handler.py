# -*- coding: utf-8 -*-
"""UPnP event handler module."""

import asyncio
import logging
import weakref
from datetime import timedelta
from http import HTTPStatus
from socket import AddressFamily  # pylint: disable=no-name-in-module
from typing import Dict, Mapping, Optional, Tuple, Union
from urllib.parse import urlparse

import defusedxml.ElementTree as DET

from async_upnp_client.client import UpnpRequester, UpnpService
from async_upnp_client.const import NS, ServiceId
from async_upnp_client.exceptions import (
    UpnpConnectionError,
    UpnpError,
    UpnpResponseError,
    UpnpSIDError,
)
from async_upnp_client.utils import async_get_local_ip, get_local_ip

_LOGGER = logging.getLogger(__name__)


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
        self._subscriptions: weakref.WeakValueDictionary[
            ServiceId, UpnpService
        ] = weakref.WeakValueDictionary()
        self._backlog: Dict[ServiceId, Tuple[Mapping, str]] = {}

    @property
    def callback_url(self) -> str:
        """Return callback URL on which we are callable.

        This URL should work for most cases, but makes assumptions about how
        a device will connect. Use callback_url_for_service to get a more
        specific URL.
        """
        if not self._listen_ip:
            self._listen_ip = get_local_ip()
        port = self.listen_ports.get(AddressFamily.AF_INET)
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
        device_host = urlparse(service.device.device_url).netloc
        addr_family, local_host = await async_get_local_ip(device_host)
        port = self.listen_ports[addr_family]

        return self._callback_url.format(host=local_host, port=port)

    def sid_for_service(self, service: UpnpService) -> Optional[ServiceId]:
        """Get the service connected to SID."""
        for sid, subscribed_service in self._subscriptions.items():
            if subscribed_service == service:
                return sid

        return None

    def service_for_sid(self, sid: ServiceId) -> Optional[UpnpService]:
        """Get a UpnpService for SID."""
        return self._subscriptions.get(sid)

    def _sid_and_service(
        self, service_or_sid: Union[UpnpService, ServiceId]
    ) -> Tuple[ServiceId, UpnpService]:
        """Resolve a SID or service to both SID and service.

        :raise KeyError: Cannot determine SID from UpnpService, or vice versa.
        """
        sid: Optional[ServiceId]
        service: Optional[UpnpService]

        if isinstance(service_or_sid, UpnpService):
            service = service_or_sid
            sid = self.sid_for_service(service)
            if not sid:
                raise KeyError(f"Unknown UpnpService {service}")
        else:
            sid = service_or_sid
            service = self.service_for_sid(sid)
            if not service:
                raise KeyError(f"Unknown SID {sid}")

        return sid, service

    async def handle_notify(self, headers: Mapping[str, str], body: str) -> HTTPStatus:
        """Handle a NOTIFY request."""
        # ensure valid request
        if "NT" not in headers or "NTS" not in headers:
            return HTTPStatus.BAD_REQUEST

        if (
            headers["NT"] != "upnp:event"
            or headers["NTS"] != "upnp:propchange"
            or "SID" not in headers
        ):
            return HTTPStatus.PRECONDITION_FAILED

        sid: ServiceId = headers["SID"]
        service = self._subscriptions.get(sid)

        # SID not known yet? store it in the backlog
        # Some devices don't behave nicely and send events before the SUBSCRIBE call is done.
        if not service:
            _LOGGER.debug("Storing NOTIFY in backlog for SID: %s", sid)
            self._backlog[sid] = (
                headers,
                body,
            )

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
        service.notify_changed_state_variables(changes)

        return HTTPStatus.OK

    async def async_subscribe(
        self,
        service: UpnpService,
        timeout: timedelta = timedelta(seconds=1800),
    ) -> Tuple[ServiceId, timedelta]:
        """
        Subscription to a UpnpService.

        Be sure to re-subscribe before the subscription timeout passes.

        :param service: UpnpService to subscribe to self
        :param timeout: Timeout of subscription
        :return: SID (subscription ID), renewal timeout (may be different to
            supplied timeout)
        :raise UpnpResponseError: Error in response to subscription request
        :raise UpnpSIDError: No SID received for subscription
        :raise UpnpConnectionError: Device might be offline.
        :raise UpnpCommunicationError (or subclass): Error while performing
            subscription request.
        """
        callback_url = await self.async_callback_url_for_service(service)

        _LOGGER.debug("Subscribing to: %s, callback URL: %s", service, callback_url)

        # do SUBSCRIBE request
        headers = {
            "NT": "upnp:event",
            "TIMEOUT": "Second-" + str(timeout.seconds),
            "HOST": urlparse(service.event_sub_url).netloc,
            "CALLBACK": f"<{callback_url}>",
        }
        response_status, response_headers, _ = await self._requester.async_http_request(
            "SUBSCRIBE", service.event_sub_url, headers
        )

        # check results
        if response_status != 200:
            _LOGGER.debug("Did not receive 200, but %s", response_status)
            raise UpnpResponseError(status=response_status, headers=response_headers)

        if "sid" not in response_headers:
            _LOGGER.debug("No SID received, aborting subscribe")
            raise UpnpSIDError

        # Device can give a different TIMEOUT header than what we have provided.
        if (
            "timeout" in response_headers
            and response_headers["timeout"] != "Second-infinite"
            and "Second-" in response_headers["timeout"]
        ):
            response_timeout = response_headers["timeout"]
            timeout_seconds = int(response_timeout[7:])  # len("Second-") == 7
            timeout = timedelta(seconds=timeout_seconds)

        sid: ServiceId = response_headers["sid"]
        self._subscriptions[sid] = service
        _LOGGER.debug("Got SID: %s, timeout: %s", sid, timeout)

        # replay any backlog we have for this service
        if sid in self._backlog:
            _LOGGER.debug("Re-playing backlogged NOTIFY for SID: %s", sid)
            item = self._backlog[sid]
            await self.handle_notify(item[0], item[1])
            del self._backlog[sid]

        return sid, timeout

    async def _async_do_resubscribe(
        self,
        service: UpnpService,
        sid: ServiceId,
        timeout: timedelta = timedelta(seconds=1800),
    ) -> Tuple[ServiceId, timedelta]:
        """Perform only a resubscribe, caller can retry subscribe if this fails."""
        # do SUBSCRIBE request
        headers = {
            "HOST": urlparse(service.event_sub_url).netloc,
            "SID": sid,
            "TIMEOUT": "Second-" + str(timeout.total_seconds()),
        }
        response_status, response_headers, _ = await self._requester.async_http_request(
            "SUBSCRIBE", service.event_sub_url, headers
        )

        # check results
        if response_status != 200:
            _LOGGER.debug("Did not receive 200, but %s", response_status)
            raise UpnpResponseError(status=response_status, headers=response_headers)

        # Devices should return the SID when re-subscribe,
        # but in case it doesn't, use the new SID.
        if "sid" in response_headers and response_headers["sid"]:
            new_sid: ServiceId = response_headers["sid"]
            if new_sid != sid:
                del self._subscriptions[sid]
                sid = new_sid

        # Device can give a different TIMEOUT header than what we have provided.
        if (
            "timeout" in response_headers
            and response_headers["timeout"] != "Second-infinite"
            and "Second-" in response_headers["timeout"]
        ):
            response_timeout = response_headers["timeout"]
            timeout_seconds = int(response_timeout[7:])  # len("Second-") == 7
            timeout = timedelta(seconds=timeout_seconds)

        self._subscriptions[sid] = service
        _LOGGER.debug("Got SID: %s, timeout: %s", sid, timeout)

        return sid, timeout

    async def async_resubscribe(
        self,
        service_or_sid: Union[UpnpService, ServiceId],
        timeout: timedelta = timedelta(seconds=1800),
    ) -> Tuple[ServiceId, timedelta]:
        """Renew subscription to a UpnpService.

        :param service_or_sid: UpnpService or existing SID to resubscribe
        :param timeout: Timeout of subscription
        :return: SID (subscription ID), renewal timeout (may be different to
            supplied timeout)
        :raise KeyError: Supplied service_or_sid is not known.
        :raise UpnpResponseError: Error in response to subscription request
        :raise UpnpSIDError: No SID received for subscription
        :raise UpnpConnectionError: Device might be offline.
        :raise UpnpCommunicationError (or subclass): Error while performing
            subscription request.
        """
        _LOGGER.debug("Resubscribing to: %s", service_or_sid)

        # Try a regular resubscribe. If that fails, delete old subscription and
        # do a full subscribe again.

        sid, service = self._sid_and_service(service_or_sid)
        try:
            return await self._async_do_resubscribe(service, sid, timeout)
        except UpnpConnectionError as err:
            _LOGGER.debug(
                "Resubscribe for %s failed: %s. Device offline, not retrying.",
                service_or_sid,
                err,
            )
            del self._subscriptions[sid]
            raise
        except UpnpError as err:
            _LOGGER.debug(
                "Resubscribe for %s failed: %s. Trying full subscribe.",
                service_or_sid,
                err,
            )
        del self._subscriptions[sid]
        return await self.async_subscribe(service, timeout)

    async def async_resubscribe_all(self) -> None:
        """Renew all current subscription."""
        await asyncio.gather(
            *(self.async_resubscribe(sid) for sid in self._subscriptions)
        )

    async def async_unsubscribe(
        self,
        service_or_sid: Union[UpnpService, ServiceId],
    ) -> ServiceId:
        """Unsubscribe from a UpnpService."""
        sid, service = self._sid_and_service(service_or_sid)

        _LOGGER.debug(
            "Unsubscribing from SID: %s, service: %s device: %s",
            sid,
            service,
            service.device,
        )

        # Remove registration before potential device errors
        del self._subscriptions[sid]

        # do UNSUBSCRIBE request
        headers = {
            "HOST": urlparse(service.event_sub_url).netloc,
            "SID": sid,
        }
        response_status, response_headers, _ = await self._requester.async_http_request(
            "UNSUBSCRIBE", service.event_sub_url, headers
        )

        # check results
        if response_status != 200:
            _LOGGER.debug("Did not receive 200, but %s", response_status)
            raise UpnpResponseError(status=response_status, headers=response_headers)

        return sid

    async def async_unsubscribe_all(self) -> None:
        """Unsubscribe all subscriptions."""
        sids = list(self._subscriptions)
        await asyncio.gather(
            *(self.async_unsubscribe(sid) for sid in sids),
            return_exceptions=True,
        )
