# -*- coding: utf-8 -*-
"""UPnP DLNA module."""

import asyncio
import logging
import re
from urllib.parse import quote_plus
from urllib.parse import urlparse
from urllib.parse import urlunparse

from datetime import timedelta
from typing import Any
from typing import Dict
from typing import List
from typing import Mapping
from typing import Optional
from xml.etree import ElementTree as ET

from didl_lite import didl_lite

from async_upnp_client import UpnpError
from async_upnp_client import UpnpService
from async_upnp_client import UpnpStateVariable
from async_upnp_client.profile import UpnpProfileDevice


_LOGGER = logging.getLogger(__name__)


SUBSCRIBE_TIMEOUT = timedelta(seconds=30 * 60)
STATE_ON = 'ON'
STATE_PLAYING = 'PLAYING'
STATE_PAUSED = 'PAUSED'
STATE_IDLE = 'IDLE'


def dlna_handle_notify_last_change(state_var: UpnpStateVariable):
    """
    Handle changes to LastChange state variable.

    This expands all changed state variables in the LastChange state variable.
    Note that the callback is called twice:
    - for the original event;
    - for the expanded event, via this function.
    """
    if state_var.name != 'LastChange':
        raise UpnpError('Call this only on state variable LastChange')

    service = state_var.service
    changes = {}

    el_event = ET.fromstring(state_var.value)
    for el_instance in el_event:
        if not el_instance.tag.endswith("}InstanceID"):
            continue

        if el_instance.attrib['val'] != '0':
            _LOGGER.warning('Only InstanceID 0 is supported')
            continue

        for el_state_var in el_instance:
            name = el_state_var.tag.split('}')[1]
            value = el_state_var.attrib['val']
            changes[name] = value

    service.notify_changed_state_variables(changes)


class DmrDevice(UpnpProfileDevice):
    """Representation of a DLNA DMR device."""

    # pylint: disable=too-many-public-methods

    _SERVICE_TYPES = {
        'RC': {
            'urn:schemas-upnp-org:service:RenderingControl:3',
            'urn:schemas-upnp-org:service:RenderingControl:2',
            'urn:schemas-upnp-org:service:RenderingControl:1',
        },
        'AVT': {
            'urn:schemas-upnp-org:service:AVTransport:3',
            'urn:schemas-upnp-org:service:AVTransport:2',
            'urn:schemas-upnp-org:service:AVTransport:1',
        },
    }

    def _interesting_service(self, service: UpnpService) -> bool:
        """Check if service is a service we're interested in."""
        # pylint: disable=no-self-use
        service_type = service.service_type
        for service_types in self._SERVICE_TYPES.values():
            if service_type in service_types:
                return True

        return False

    async def async_subscribe_services(self) -> timedelta:
        """(Re-)Subscribe to services."""
        for service in self._device.services.values():
            # ensure we are interested in this service_type
            if not self._interesting_service(service):
                continue

            service.on_event = self._on_event
            if self._event_handler.sid_for_service(service) is None:
                _LOGGER.debug('Subscribing to service: %s', service)
                await self._event_handler.async_subscribe(service, timeout=SUBSCRIBE_TIMEOUT)
            else:
                _LOGGER.debug('Resubscribing to service: %s', service)
                await self._event_handler.async_resubscribe(service, timeout=SUBSCRIBE_TIMEOUT)

        return SUBSCRIBE_TIMEOUT

    async def async_unsubscribe_services(self):
        """Unsubscribe from all subscribed services."""
        await self._event_handler.async_unsubscribe_all()

    async def async_update(self):
        """Retrieve the latest data."""
        # call GetTransportInfo/GetPositionInfo regularly
        avt_service = self._service('AVT')
        if avt_service:
            await self._async_poll_transport_info()

            if self.state == STATE_PLAYING or \
               self.state == STATE_PAUSED:
                # playing something, get position info
                await self._async_poll_position_info()
        else:
            await self._device.async_ping()

    async def _async_poll_transport_info(self):
        """Update transport info from device."""
        action = self._action('AVT', 'GetTransportInfo')
        result = await action.async_call(InstanceID=0)

        # set/update state_variable 'TransportState'
        changed = []
        state_var = self._state_variable('AVT', 'TransportState')
        if state_var.value != result['CurrentTransportState']:
            state_var.value = result['CurrentTransportState']
            changed.append(state_var)

        service = action.service
        self._on_event(service, changed)

    async def _async_poll_position_info(self):
        """Update position info."""
        action = self._action('AVT', 'GetPositionInfo')
        result = await action.async_call(InstanceID=0)

        changed = []
        track_duration = self._state_variable('AVT', 'CurrentTrackDuration')
        if track_duration.value != result['TrackDuration']:
            track_duration.value = result['TrackDuration']
            changed.append(track_duration)

        time_position = self._state_variable('AVT', 'RelativeTimePosition')
        if time_position.value != result['RelTime']:
            time_position.value = result['RelTime']
            changed.append(time_position)

        service = action.service
        self._on_event(service, changed)

    def _on_event(self, service: UpnpService, state_variables: List[UpnpStateVariable]):
        """State variable(s) changed, let home-assistant know."""
        for state_variable in state_variables:
            if state_variable.name == 'LastChange':
                dlna_handle_notify_last_change(state_variable)

        if self.on_event:
            # pylint: disable=not-callable
            self.on_event(service, state_variables)

    @property
    def state(self):
        """Get current state."""
        state_var = self._state_variable('AVT', 'TransportState')
        if not state_var:
            return STATE_ON

        state_value = (state_var.value or '').strip().lower()
        if state_value == 'playing':
            return STATE_PLAYING
        if state_value == 'paused':
            return STATE_PAUSED

        return STATE_IDLE

    @property
    def _current_transport_actions(self):
        state_var = self._state_variable('AVT', 'CurrentTransportActions')
        transport_actions = (state_var.value or '').split(',')
        return [a.lower().strip() for a in transport_actions]

    def _supports(self, var_name: str) -> bool:
        return self._state_variable('RC', var_name) is not None and \
            self._action('RC', 'Set%s' % var_name) is not None

    def _level(self, var_name: str) -> Optional[float]:
        state_var = self._state_variable('RC', var_name)
        value = state_var.value
        if value is None:
            _LOGGER.debug('Got no value for %s', var_name)
            return None

        max_value = state_var.max_value or 100
        return min(value / max_value, 1.0)

    async def _async_set_level(self, var_name: str, level: float, **kwargs: Dict[str, Any]) -> None:
        action = self._action('RC', 'Set%s' % var_name)
        argument = action.argument('Desired%s' % var_name)
        state_variable = argument.related_state_variable
        min_ = state_variable.min_value or 0
        max_ = state_variable.max_value or 100
        desired_level = int(min_ + level * (max_ - min_))
        args = kwargs.copy()
        args.update({'Desired%s' % var_name: desired_level})

        await action.async_call(InstanceID=0, **args)

# region RC/Picture
    @property
    def has_brightness_level(self) -> bool:
        """Check if device has brightness level controls."""
        return self._supports('Brightness')

    @property
    def brightness_level(self) -> Optional[float]:
        """Brightness level of the media player (0..1)."""
        return self._level('Brightness')

    async def async_set_brightness_level(self, brightness: float) -> None:
        """Set brightness level, range 0..1."""
        await self._async_set_level('Brightness', brightness)

    @property
    def has_contrast_level(self) -> bool:
        """Check if device has contrast level controls."""
        return self._supports('Contrast')

    @property
    def contrast_level(self) -> Optional[float]:
        """Contrast level of the media player (0..1)."""
        return self._level('Contrast')

    async def async_set_contrast_level(self, contrast: float) -> None:
        """Set contrast level, range 0..1."""
        await self._async_set_level('Contrast', contrast)

    @property
    def has_sharpness_level(self) -> bool:
        """Check if device has sharpness level controls."""
        return self._supports('Sharpness')

    @property
    def sharpness_level(self) -> Optional[float]:
        """Sharpness level of the media player (0..1)."""
        return self._level('Sharpness')

    async def async_set_sharpness_level(self, sharpness: float) -> None:
        """Set sharpness level, range 0..1."""
        await self._async_set_level('Sharpness', sharpness)

    @property
    def has_color_temperature_level(self) -> bool:
        """Check if device has color temperature level controls."""
        return self._supports('ColorTemperature')

    @property
    def color_temperature_level(self) -> Optional[float]:
        """Color temperature level of the media player (0..1)."""
        return self._level('ColorTemperature')

    async def async_set_color_temperature_level(self, color_temperature: float):
        """Set color temperature level, range 0..1."""
        await self._async_set_level('ColorTemperature', color_temperature)
# endregion

# region RC/Volume
    @property
    def has_volume_level(self):
        """Check if device has Volume level controls."""
        return self._supports('Volume')

    @property
    def volume_level(self):
        """Volume level of the media player (0..1)."""
        return self._level('Volume')

    async def async_set_volume_level(self, volume: float):
        """Set volume level, range 0..1."""
        await self._async_set_level('Volume', volume, Channel='Master')

    @property
    def has_volume_mute(self):
        """Check if device has Volume mute controls."""
        return self._supports('Mute')

    @property
    def is_volume_muted(self):
        """Boolean if volume is currently muted."""
        state_var = self._state_variable('RC', 'Mute')
        value = state_var.value
        if value is None:
            _LOGGER.debug('Got no value for volume_mute')
            return None

        return value

    async def async_mute_volume(self, mute):
        """Mute the volume."""
        action = self._action('RC', 'SetMute')
        desired_mute = bool(mute)

        await action.async_call(InstanceID=0,
                                Channel='Master',
                                DesiredMute=desired_mute)
# endregion

# region AVT/Transport actions
    @property
    def has_pause(self):
        """Check if device has Pause controls."""
        return self._action('AVT', 'Pause') is not None

    @property
    def can_pause(self):
        """Check if the device can currently Pause."""
        return self.has_pause and \
            'pause' in self._current_transport_actions

    async def async_pause(self):
        """Send pause command."""
        if 'pause' not in self._current_transport_actions:
            _LOGGER.debug('Cannot do Pause')
            return

        action = self._action('AVT', 'Pause')
        await action.async_call(InstanceID=0)

    @property
    def has_play(self):
        """Check if device has Play controls."""
        return self._action('AVT', 'Play') is not None

    @property
    def can_play(self):
        """Check if the device can currently play."""
        return self.has_play and \
            'play' in self._current_transport_actions

    async def async_play(self):
        """Send play command."""
        if 'play' not in self._current_transport_actions:
            _LOGGER.debug('Cannot do Play')
            return

        action = self._action('AVT', 'Play')
        await action.async_call(InstanceID=0, Speed='1')

    @property
    def can_stop(self):
        """Check if the device can currently stop."""
        return self.has_stop and \
            'stop' in self._current_transport_actions

    @property
    def has_stop(self):
        """Check if device has Play controls."""
        return self._action('AVT', 'Stop') is not None

    async def async_stop(self):
        """Send stop command."""
        if 'stop' not in self._current_transport_actions:
            _LOGGER.debug('Cannot do Stop')
            return

        action = self._action('AVT', 'Stop')
        await action.async_call(InstanceID=0)

    @property
    def has_previous(self):
        """Check if device has Previous controls."""
        return self._action('AVT', 'Previous')

    @property
    def can_previous(self):
        """Check if the device can currently Previous."""
        return self.has_previous and \
            'previous' in self._current_transport_actions

    async def async_previous(self):
        """Send previous track command."""
        if 'previous' not in self._current_transport_actions:
            _LOGGER.debug('Cannot do Previous')
            return

        action = self._action('AVT', 'Previous')
        await action.async_call(InstanceID=0)

    @property
    def has_next(self):
        """Check if device has Next controls."""
        return self._action('AVT', 'Next') is not None

    @property
    def can_next(self):
        """Check if the device can currently Next."""
        return self.has_next and \
            'next' in self._current_transport_actions

    async def async_next(self):
        """Send next track command."""
        if 'next' not in self._current_transport_actions:
            _LOGGER.debug('Cannot do Next')
            return

        action = self._action('AVT', 'Next')
        await action.async_call(InstanceID=0)

    @property
    def has_play_media(self):
        """Check if device has Play controls."""
        return self._action('AVT', 'SetAVTransportURI') is not None

    async def async_set_transport_uri(self, media_url, media_title, mime_type, upnp_class):
        """Play a piece of media."""
        # escape media_url
        _LOGGER.debug('Set transport uri: %s', media_url)
        media_url_parts = urlparse(media_url)
        media_url = urlunparse([
            media_url_parts.scheme,
            media_url_parts.netloc,
            media_url_parts.path,
            None,
            quote_plus(media_url_parts.query),
            None])

        # queue media
        meta_data = await self._construct_play_media_metadata(media_url,
                                                              media_title,
                                                              mime_type,
                                                              upnp_class)
        action = self._action('AVT', 'SetAVTransportURI')
        await action.async_call(InstanceID=0,
                                CurrentURI=media_url,
                                CurrentURIMetaData=meta_data)

    async def async_wait_for_can_play(self, max_wait_time=5):
        """Wait for play command to be ready."""
        loop_time = 0.25
        count = int(max_wait_time / loop_time)
        # wait for state variable AVT.AVTransportURI to change and
        for _ in range(count):
            if 'play' in self._current_transport_actions:
                break
            await asyncio.sleep(loop_time)
        else:
            _LOGGER.debug('break out of waiting game')

    async def _fetch_headers(self, url: str, headers: Mapping):
        """Do a HEAD/GET to get resources headers."""
        requester = self._device.requester

        # try a HEAD first
        status, headers, _ = await requester.async_http_request('HEAD',
                                                                url,
                                                                headers=headers,
                                                                body_type='ignore')
        if 200 <= status < 300:
            return headers

        # then try a GET
        status, headers, _ = await requester.async_http_request('GET',
                                                                url,
                                                                headers=headers,
                                                                body_type='ignore')
        if 200 <= status < 300:
            return headers

        return None

    async def _construct_play_media_metadata(self, media_url, media_title, mime_type, upnp_class):
        """Construct the metadata for play_media command."""
        media_info = {
            'mime_type': mime_type,
            'dlna_features': 'DLNA.ORG_OP=01;DLNA.ORG_CI=0;'
                             'DLNA.ORG_FLAGS=00000000000000000000000000000000',
        }

        # do a HEAD/GET, to retrieve content-type/mime-type
        try:
            headers = await self._fetch_headers(media_url, {'GetContentFeatures.dlna.org': '1'})
            if headers:
                if 'Content-Type' in headers:
                    media_info['mime_type'] = headers['Content-Type']

                if 'ContentFeatures.dlna.org' in headers:
                    media_info['dlna_features'] = headers['contentFeatures.dlna.org']
        except Exception:  # pylint: disable=broad-except
            pass

        # build DIDL-Lite item + resource
        protocol_info = "http-get:*:{mime_type}:{dlna_features}".format(**media_info)
        resource = didl_lite.Resource(uri=media_url, protocol_info=protocol_info)
        didl_item_type = didl_lite.type_by_upnp_class(upnp_class)
        item = didl_item_type(id="0", parent_id="0", title=media_title,
                              restricted="1", resources=[resource])

        return didl_lite.to_xml_string(item).decode('utf-8')

    @property
    def media_title(self):
        """Title of current playing media."""
        state_var = self._state_variable('AVT', 'CurrentTrackMetaData')
        if state_var is None:
            return None

        xml = state_var.value
        if not xml or xml == 'NOT_IMPLEMENTED':
            return None

        items = didl_lite.from_xml_string(xml)
        if not items:
            return None

        item = items[0]
        return item.title

    @property
    def media_image_url(self):
        """Image url of current playing media."""
        state_var = self._state_variable('AVT', 'CurrentTrackMetaData')
        if state_var is None:
            return None

        xml = state_var.value
        if not xml or xml == 'NOT_IMPLEMENTED':
            return None

        items = didl_lite.from_xml_string(xml)
        if not items:
            return None

        for item in items:
            for res in item.resources:
                protocol_info = res.protocol_info
                if protocol_info.startswith('http-get:*:image/'):
                    return res.url

        return None

    @property
    def media_duration(self):
        """Duration of current playing media in seconds."""
        state_var = self._state_variable('AVT', 'CurrentTrackDuration')
        if state_var is None or \
           state_var.value is None or \
           state_var.value == 'NOT_IMPLEMENTED':
            return None

        split = [int(v) for v in re.findall(r"[\w']+", state_var.value)]
        delta = timedelta(hours=split[0], minutes=split[1], seconds=split[2])
        return delta.seconds

    @property
    def media_position(self):
        """Position of current playing media in seconds."""
        state_var = self._state_variable('AVT', 'RelativeTimePosition')
        if state_var is None or \
           state_var.value is None or \
           state_var.value == 'NOT_IMPLEMENTED':
            return None

        split = [int(v) for v in re.findall(r"[\w']+", state_var.value)]
        delta = timedelta(hours=split[0], minutes=split[1], seconds=split[2])
        return delta.seconds

    @property
    def media_position_updated_at(self):
        """
        When was the position of the current playing media valid.

        Returns value from homeassistant.util.dt.utcnow().
        """
        state_var = self._state_variable('AVT', 'RelativeTimePosition')
        if state_var is None:
            return None

        return state_var.updated_at
# endregion
