# -*- coding: utf-8 -*-
"""UPnP event handler module."""

import logging
import urllib.parse
from datetime import datetime, timedelta
from http import HTTPStatus
from typing import Dict, Mapping, NamedTuple, Optional, Tuple

import defusedxml.ElementTree as DET

from async_upnp_client.client import UpnpError, UpnpRequester, UpnpService
from async_upnp_client.const import NS

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

    def __init__(self, callback_url: str, requester: UpnpRequester) -> None:
        """Initialize."""
        self._callback_url = callback_url
        self._requester = requester

        self._subscriptions: Dict[str, SubscriptionInfo] = {}
        self._backlog: Dict[str, Tuple[Mapping, str]] = {}

    @property
    def callback_url(self) -> str:
        """Return callback URL on which we are callable."""
        return self._callback_url

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
        body = body.strip().strip("\u0000")
        el_root = DET.fromstring(body)
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
        service: "UpnpService",
        timeout: timedelta = timedelta(seconds=1800),
    ) -> Tuple[bool, Optional[str]]:
        """
        Subscription to a UpnpService.

        Be sure to re-subscribe before the subscription timeout passes.

        :param service UpnpService to subscribe to self
        :param timeout Timeout of subscription
        """
        _LOGGER.debug(
            "Subscribing to: %s, callback URL: %s", service, self.callback_url
        )

        # do SUBSCRIBE request
        headers = {
            "NT": "upnp:event",
            "TIMEOUT": "Second-" + str(timeout.seconds),
            "HOST": urllib.parse.urlparse(service.event_sub_url).netloc,
            "CALLBACK": "<{}>".format(self.callback_url),
        }
        response_status, response_headers, _ = await self._requester.async_http_request(
            "SUBSCRIBE", service.event_sub_url, headers
        )

        # check results
        if response_status != 200:
            _LOGGER.debug("Did not receive 200, but %s", response_status)
            return False, None

        if "sid" not in response_headers:
            _LOGGER.debug("No SID received, aborting subscribe")
            return False, None

        sid = response_headers["sid"]
        renewal_time = datetime.now() + timeout
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

        return True, sid

    async def async_resubscribe(
        self,
        service: "UpnpService",
        timeout: timedelta = timedelta(seconds=1800),
    ) -> Tuple[bool, Optional[str]]:
        """Renew subscription to a UpnpService."""
        _LOGGER.debug("Resubscribing to: %s", service)

        # do SUBSCRIBE request
        sid = self.sid_for_service(service)
        if not sid:
            raise UpnpError("Could not find SID for service")

        headers = {
            "HOST": urllib.parse.urlparse(service.event_sub_url).netloc,
            "SID": sid,
            "TIMEOUT": "Second-" + str(timeout.seconds),
        }
        response_status, response_headers, _ = await self._requester.async_http_request(
            "SUBSCRIBE", service.event_sub_url, headers
        )

        # check results
        if response_status != 200:
            _LOGGER.debug("Did not receive 200, but %s", response_status)
            return False, None

        # Devices should return the SID when re-subscribe,
        # but in case it doesn't, use the new SID.
        if "sid" in response_headers and response_headers["sid"]:
            new_sid: str = response_headers["sid"]
            if new_sid != sid:
                del self._subscriptions[sid]
                sid = new_sid

        renewal_time = datetime.now() + timeout
        self._subscriptions[sid] = SubscriptionInfo(
            service=service,
            timeout=timeout,
            renewal_time=renewal_time,
        )
        _LOGGER.debug("Got SID: %s, renewal_time: %s", sid, renewal_time)

        return True, sid

    async def async_resubscribe_all(self) -> None:
        """Renew all current subscription."""
        for entry in self._subscriptions.values():
            service = entry.service
            await self.async_resubscribe(service)

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
        for entry in services.values():
            service = entry.service
            await self.async_unsubscribe(service)
