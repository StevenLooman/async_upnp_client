# -*- coding: utf-8 -*-
"""async_upnp_client profile for Open Home Media players.

This profile has many convenience methods for invoking an action from an Open Home service
Not all devices will offer all services and actions. If a service or action is not available
then a warning will be issued and no error or action will be taken
"""

# pylint: disable=too-many-lines
import base64
import binascii
import logging
import struct
import xml.etree.ElementTree as ET

try:
    from enum import StrEnum
except ImportError:
    from backports.strenum import StrEnum
from typing import Any, Mapping, Sequence

from async_upnp_client.client import UpnpDevice, UpnpService, UpnpStateVariable
from async_upnp_client.event_handler import UpnpEventHandler
from async_upnp_client.profiles.profile import UpnpProfileDevice

_LOGGER = logging.getLogger(__name__)


# region Service and other enums
class Service(StrEnum):
    """Linn/Open Home Network Services."""

    CREDENTIALS = "Credentials"
    INFO = "Info"
    PINS = "Pins"
    PLAYLIST = "Playlist"
    PRODUCT = "Product"
    RADIO = "Radio"
    RECEIVER = "Receiver"
    SENDER = "Sender"
    TIME = "Time"
    TRANSPORT = "Transport"
    UPDATE = "Update"
    VOLUME = "Volume"


class ServiceId(StrEnum):
    """Linn/Open Home Network Service Ids."""

    # OPENHOME
    CREDENTIALS = "urn:av-openhome-org:serviceId:Credentials"
    INFO = "urn:av-openhome-org:serviceId:Info"
    PINS = "urn:av-openhome-org:serviceId:Pins"
    PLAYLIST = "urn:av-openhome-org:serviceId:Playlist"
    PLAYLISTMANAGER = "urn:av-openhome-org:serviceId:PlaylistManager"
    PRODUCT = "urn:av-openhome-org:serviceId:Product"
    RADIO = "urn:av-openhome-org:serviceId:Radio"
    RECEIVER = "urn:av-openhome-org:serviceId:Receiver"
    SENDER = "urn:av-openhome-org:serviceId:Sender"
    TIME = "urn:av-openhome-org:serviceId:Time"
    TRANSPORT = "urn:av-openhome-org:serviceId:Transport"
    VOLUME = "urn:av-openhome-org:serviceId:Volume"
    # LINN
    DIAGNOSTICS = "urn:linn-co-uk:serviceId:Diagnostics"
    PRIVACY = "urn:linn-co-uk:serviceId:Privacy"
    UPDATE = "urn:linn-co-uk:serviceId:Update"
    VOLKANO = "urn:linn-co-uk:serviceId:Volkano"


class ProductSourceType(StrEnum):
    """Supported values for Product Source Type."""

    ANALOG = "Analog"  # Specifies an analog external input
    DIGITAL = "Digital"  # Specifies a digital external input
    HDMI = "Hdmi"  # Specifies a HDMI external input
    NETAUX = "NetAux"  # Specifies 3rd party, non OpenHome controllable, network protocols such as AirPlay
    PLAYLIST = "Playlist"  # the av.openhome.org:Playlist:1 service must be available
    RADIO = "Radio"  # the av.openhome.org:Radio:1 service must be available
    RECEIVER = "Receiver"  # the av.openhome.org:Receiver:1 service must be available
    UPNPAV = "UpnpAv"  # the upnp.org:MediaRenderer:1 device must be available


# endregion


# region Action Enums
class Credentials(StrEnum):
    """Actions for Credentials Service."""

    SET = "Set"
    CLEAR = "Clear"
    SET_ENABLED = "SetEnabled"
    GET = "Get"
    LOGIN = "Login"
    RE_LOGIN = "ReLogin"
    GET_IDS = "GetIds"
    GET_PUBLIC_KEY = "GetPublicKey"
    GET_SEQUENCE_NUMBER = "GetSequenceNumber"


class Info(StrEnum):
    """Actions for Info Service."""

    COUNTERS = "Counters"
    TRACK = "Track"
    DETAILS = "Details"
    METATEXT = "Metatext"


class Pins(StrEnum):
    """Actions for Pins Service."""

    GET_DEVICE_MAX = "GetDeviceMax"
    GET_ACCOUNT_MAX = "GetAccountMax"
    GET_MODES = "GetModes"
    GET_ID_ARRAY = "GetIdArray"
    GET_CLOUD_CONNECTED = "GetCloudConnected"
    READ_LIST = "ReadList"
    INVOKE_ID = "InvokeId"
    INVOKE_INDEX = "InvokeIndex"
    INVOKE_URI = "InvokeUri"
    SET_DEVICE = "SetDevice"
    SET_ACCOUNT = "SetAccount"
    CLEAR = "Clear"
    SWAP = "Swap"


class Playlist(StrEnum):
    """Actions for Playlist Service."""

    PLAY = "Play"
    PAUSE = "Pause"
    STOP = "Stop"
    NEXT = "Next"
    PREVIOUS = "Previous"
    SET_REPEAT = "SetRepeat"
    REPEAT = "Repeat"
    SET_SHUFFLE = "SetShuffle"
    SHUFFLE = "Shuffle"
    SEEK_SECOND_ABSOLUTE = "SeekSecondAbsolute"
    SEEK_SECOND_RELATIVE = "SeekSecondRelative"
    SEEK_ID = "SeekId"
    SEEK_INDEX = "SeekIndex"
    TRANSPORT_STATE = "TransportState"
    ID = "Id"
    READ = "Read"
    READ_LIST = "ReadList"
    INSERT = "Insert"
    DELETE_ID = "DeleteId"
    DELETE_ALL = "DeleteAll"
    TRACKS_MAX = "TracksMax"
    ID_ARRAY = "IdArray"
    ID_ARRAY_CHANGED = "IdArrayChanged"
    PROTOCOL_INFO = "ProtocolInfo"


class Product(StrEnum):
    """Actions for Product Service."""

    MANUFACTURER = "Manufacturer"
    MODEL = "Model"
    PRODUCT = "Product"
    STANDBY = "Standby"
    STANDBY_TRANSITIONING = "StandbyTransitioning"
    SET_STANDBY = "SetStandby"
    SOURCE_COUNT = "SourceCount"
    SOURCE_XML = "SourceXml"
    SOURCE_INDEX = "SourceIndex"
    SET_SOURCE_INDEX = "SetSourceIndex"
    SET_SOURCE_INDEX_BY_NAME = "SetSourceIndexByName"
    SET_SOURCE_BY_SYSTEM_NAME = "SetSourceBySystemName"
    SOURCE = "Source"
    ATTRIBUTES = "Attributes"
    SOURCE_XML_CHANGE_COUNT = "SourceXmlChangeCount"
    GET_IMAGE_URI = "GetImageUri"


class Radio(StrEnum):
    """Actions for Radio Service."""

    REFRESH_PRESETS = "RefreshPresets"
    PLAY = "Play"
    PAUSE = "Pause"
    STOP = "Stop"
    SEEK_SECOND_ABSOLUTE = "SeekSecondAbsolute"
    SEEK_SECOND_RELATIVE = "SeekSecondRelative"
    CHANNEL = "Channel"
    SET_CHANNEL = "SetChannel"
    TRANSPORT_STATE = "TransportState"
    ID = "Id"
    SET_ID = "SetId"
    READ = "Read"
    READ_LIST = "ReadList"
    ID_ARRAY = "IdArray"
    ID_ARRAY_CHANGED = "IdArrayChanged"
    CHANNELS_MAX = "ChannelsMax"
    PROTOCOL_INFO = "ProtocolInfo"


class Receiver(StrEnum):
    """Actions for Receiver Service."""

    PLAY = "Play"
    STOP = "Stop"
    SET_SENDER = "SetSender"
    SENDER = "Sender"
    PROTOCOL_INFO = "ProtocolInfo"
    TRANSPORT_STATE = "TransportState"


class Sender(StrEnum):
    """Actions for Sender Service."""

    PRESENTATION_URL = "PresentationUrl"
    METADATA = "Metadata"
    AUDIO = "Audio"
    STATUS = "Status"
    STATUS2 = "Status2"
    ENABLED = "Enabled"
    ATTRIBUTES = "Attributes"


class Time(StrEnum):
    """Actions for Time Service."""

    TIME = "Time"


class Transport(StrEnum):
    """Actions for Transport Service."""

    PLAY_AS = "PlayAs"
    PLAY = "Play"
    PAUSE = "Pause"
    STOP = "Stop"
    SKIP_NEXT = "SkipNext"
    SKIP_PREVIOUS = "SkipPrevious"
    SET_REPEAT = "SetRepeat"
    SET_SHUFFLE = "SetShuffle"
    SEEK_SECOND_ABSOLUTE = "SeekSecondAbsolute"
    SEEK_SECOND_RELATIVE = "SeekSecondRelative"
    TRANSPORT_STATE = "TransportState"
    MODES = "Modes"
    MODE_INFO = "ModeInfo"
    STREAM_INFO = "StreamInfo"
    STREAM_ID = "StreamId"
    REPEAT = "Repeat"
    SHUFFLE = "Shuffle"


class Update(StrEnum):
    """Actions for Update Service."""

    GET_SOFTWARE_STATUS = "GetSoftwareStatus"
    GET_EXECUTOR_STATUS = "GetExecutorStatus"
    GET_JOB_STATUS = "GetJobStatus"
    PUSH_MANIFEST = "PushManifest"
    PUSH_MANIFEST2 = "PushManifest2"
    APPLY = "Apply"
    APPLY2 = "Apply2"
    RECOVER = "Recover"
    RECOVER2 = "Recover2"
    RECOVER_KEEP_STORE = "RecoverKeepStore"
    RECOVER_KEEP_STORE2 = "RecoverKeepStore2"
    CHECK_NOW = "CheckNow"
    GET_RECOVER_SUPPORTED = "GetRecoverSupported"


class Volume(StrEnum):
    """Action names for Volume service."""

    CHARACTERISTICS = "Characteristics"
    SET_VOLUME = "SetVolume"
    VOLUME_INC = "VolumeInc"
    VOLUME_DEC = "VolumeDec"
    SET_VOLUME_NO_UNMUTE = "SetVolumeNoUnmute"
    VOLUME_INC_NO_UNMUTE = "VolumeIncNoUnmute"
    VOLUME_DEC_NO_UNMUTE = "VolumeDecNoUnmute"
    VOLUME = "Volume"
    SET_BALANCE = "SetBalance"
    BALANCE_INC = "BalanceInc"
    BALANCE_DEC = "BalanceDec"
    BALANCE = "Balance"
    SET_FADE = "SetFade"
    FADE_INC = "FadeInc"
    FADE_DEC = "FadeDec"
    FADE = "Fade"
    SET_MUTE = "SetMute"
    MUTE = "Mute"
    VOLUME_LIMIT = "VolumeLimit"
    UNITY_GAIN = "UnityGain"
    VOLUME_OFFSET = "VolumeOffset"
    SET_VOLUME_OFFSET = "SetVolumeOffset"
    TRIM = "Trim"
    SET_TRIM = "SetTrim"


# endregion


# region State Variable Enums
class CredentialsState(StrEnum):
    """State variable names for Credentials service."""

    IDS = "Ids"
    PUBLIC_KEY = "PublicKey"
    SEQUENCE_NUMBER = "SequenceNumber"


class InfoState(StrEnum):
    """State variable names for Info service."""

    TRACK_COUNT = "TrackCount"
    DETAILS_COUNT = "DetailsCount"
    METATEXT_COUNT = "MetatextCount"
    URI = "Uri"
    METADATA = "Metadata"
    DURATION = "Duration"
    BIT_RATE = "BitRate"
    BIT_DEPTH = "BitDepth"
    SAMPLE_RATE = "SampleRate"
    LOSSLESS = "Lossless"
    CODEC_NAME = "CodecName"
    METATEXT = "Metatext"


class PlaylistState(StrEnum):
    """State variable names for Playlist service."""

    TRANSPORT_STATE = "TransportState"
    REPEAT = "Repeat"
    SHUFFLE = "Shuffle"
    ID = "Id"
    ID_ARRAY = "IdArray"
    TRACKS_MAX = "TracksMax"
    PROTOCOL_INFO = "ProtocolInfo"


class PlaylistStateAllowedValues(StrEnum):
    """Allowed values for Playlist service."""

    BUFFERING = "Buffering"
    PAUSED = "Paused"
    PLAYING = "Playing"
    STOPPED = "Stopped"


class ProductState(StrEnum):
    """State variable names for Product service."""

    ATTRIBUTES = "Attributes"
    MANUFACTURER_IMAGE_URI = "ManufacturerImageUri"
    MANUFACTURER_INFO = "ManufacturerInfo"
    MANUFACTURER_NAME = "ManufacturerName"
    MANUFACTURER_URL = "ManufacturerUrl"
    MODEL_IMAGE_URI = "ModelImageUri"
    MODEL_INFO = "ModelInfo"
    MODEL_NAME = "ModelName"
    MODEL_URL = "ModelUrl"
    PRODUCT_IMAGE_HIRES_URI = "ProductImageHiresUri"
    PRODUCT_IMAGE_URI = "ProductImageUri"
    PRODUCT_INFO = "ProductInfo"
    PRODUCT_NAME = "ProductName"
    PRODUCT_ROOM = "ProductRoom"
    PRODUCT_URL = "ProductUrl"
    SOURCE_COUNT = "SourceCount"
    SOURCE_INDEX = "SourceIndex"
    SOURCE_NAME = "A_ARG_TYPE_Source_Name"
    SOURCE_SYSTEM_NAME = "A_ARG_TYPE_Source_SystemName"
    SOURCE_TYPE = "A_ARG_TYPE_Source_Type"
    SOURCE_VISIBLE = "A_ARG_TYPE_Source_Visible"
    SOURCE_XML = "SourceXml"
    SOURCE_XML_CHANGE_COUNT_VALUE = "A_ARG_TYPE_SourceXmlChangeCount_Value"
    STANDBY = "Standby"
    STANDBY_TRANSITIONING = "StandbyTransitioning"


class TimeState(StrEnum):
    """State variable names for Time service."""

    DURATION = "Duration"
    SECONDS = "Seconds"
    TRACK_COUNT = "TrackCount"


class TransportState(StrEnum):
    """State variable names for Transport service."""

    CAN_PAUSE = "CanPause"
    CAN_REPEAT = "CanRepeat"
    CAN_SEEK = "CanSeek"
    CAN_SHUFFLE = "CanShuffle"
    CAN_SKIP_NEXT = "CanSkipNext"
    CAN_SKIP_PREVIOUS = "CanSkipPrevious"
    MODES = "Modes"
    REPEAT = "Repeat"
    SHUFFLE = "Shuffle"
    STREAM_ID = "StreamId"
    TRANSPORT_STATE = "TransportState"


class TransportStateAllowedValues(StrEnum):
    """Allowed values for Transport service."""

    BUFFERING = "Buffering"
    PAUSED = "Paused"
    PLAYING = "Playing"
    STOPPED = "Stopped"
    WAITING = "Waiting"


class VolumeState(StrEnum):
    """State variable names for Volume service."""

    BALANCE = "Balance"
    BALANCE_MAX = "BalanceMax"
    FADE = "Fade"
    FADE_MAX = "FadeMax"
    MUTE = "Mute"
    TRIM = "A_ARG_TYPE_Trim_TrimBinaryMilliDb"
    UNITY_GAIN = "UnityGain"
    VOLUME = "Volume"
    VOLUME_LIMIT = "VolumeLimit"
    VOLUME_MAX = "VolumeMax"
    VOLUME_MILLI_DB_PER_STEP = "VolumeMilliDbPerStep"
    VOLUME_OFFSET = "A_ARG_TYPE_VolumeOffset_VolumeOffsetBinaryMilliDb"
    VOLUME_STEPS = "VolumeSteps"
    VOLUME_UNITY = "VolumeUnity"


# endregion


class OhmDevice(UpnpProfileDevice):
    """Representation of an OpenHome Media (ohMedia) device."""

    def __init__(self, device: UpnpDevice, event_handler: UpnpEventHandler | None) -> None:
        """Initialize."""
        super().__init__(device, event_handler)

    @property
    def uuid(self) -> str:
        """Return the unique device name."""
        return self.device.udn

    @property
    def manufacturer(self) -> str:
        """Return the manufacturer name."""
        return self.device.manufacturer

    @property
    def model_name(self) -> str:
        """Return the model name."""
        return self.device.model_name

    @property
    def friendly_name(self) -> str:
        """Return the friendly name of the product."""
        return self.device.friendly_name

    async def room(self) -> str | None:
        """Return the room where product is located."""
        return await self.product_room


    # endregion

    # region enums and constants
    DEVICE_TYPES = [
        "urn:linn-co-uk:device:Source:1",
    ]

    SERVICE_IDS = frozenset(
        (
            "urn:av-openhome-org:serviceId:Credentials",
            "urn:av-openhome-org:serviceId:Info",
            "urn:av-openhome-org:serviceId:Pins",
            "urn:av-openhome-org:serviceId:Playlist",
            "urn:av-openhome-org:serviceId:PlaylistManager",
            "urn:av-openhome-org:serviceId:Product",
            "urn:av-openhome-org:serviceId:Radio",
            "urn:av-openhome-org:serviceId:Receiver",
            "urn:av-openhome-org:serviceId:Sender",
            "urn:av-openhome-org:serviceId:Time",
            "urn:av-openhome-org:serviceId:Transport",
            "urn:av-openhome-org:serviceId:Volume",
            "urn:linn-co-uk:serviceId:Update",
        )
    )

    _SERVICE_TYPES = {
        "Credentials": {"urn:av-openhome-org:service:Credentials:1"},
        "Info": {"urn:av-openhome-org:service:Info:1"},
        "Pins": {"urn:av-openhome-org:service:Pins:1"},
        "Playlist": {"urn:av-openhome-org:service:Playlist:1"},
        "Product": {
            "urn:av-openhome-org:service:Product:4",
            "urn:av-openhome-org:service:Product:3",
            "urn:av-openhome-org:service:Product:2",
            "urn:av-openhome-org:service:Product:1",
        },
        "Radio": {
            "urn:av-openhome-org:service:Radio:2",
            "urn:av-openhome-org:service:Radio:1",
        },
        "Receiver": {"urn:av-openhome-org:service:Receiver:1"},
        "Sender": {
            "urn:av-openhome-org:service:Sender:2",
            "urn:av-openhome-org:service:Sender:1",
        },
        "Time": {"urn:av-openhome-org:service:Time:1"},
        "Transport": {"urn:av-openhome-org:service:Transport:1"},
        "Volume": {
            "urn:av-openhome-org:service:Volume:4",
            "urn:av-openhome-org:service:Volume:3",
            "urn:av-openhome-org:service:Volume:2",
            "urn:av-openhome-org:service:Volume:1",
        },
        "Update": {
            "urn:linn-co-uk:service:Update:4",
        },
    }
    # endregion

    # functions

    def _on_event(
        self,
        service: UpnpService,
        state_variables: Sequence[UpnpStateVariable[Any]],
    ) -> None:
        """Handle state variable(s) changed event from OHM device."""
        _LOGGER.debug("PROFILE_ON_EVENT %s", service.service_id)
        for sv in state_variables:
            state_var = service.state_variable(sv.name)
            state_var._value = sv._value
        if self.on_event:
            # pylint: disable=not-callable
            # pass control to calling event handler if on_event is overridden
            self.on_event(service, state_variables)

    # endregion

    # region Credentials Service actions
    async def credentials_set(self, ident: str, username: str, password: str) -> None:
        """Set the username and password for a given service.

        :param ident: the identifier for the service
        :param username: username for the service
        :param password: must be encrypted using the RSA public key in the PublicKey state variable
        """
        await self._async_call_action(
            Service.CREDENTIALS,
            Credentials.SET,
            Id=ident,
            UserName=username,
            Password=password,
        )

    async def credentials_clear(self, ident: str) -> None:
        """Remove both username and password for a given service.

        :param ident: the identifier for the service
        """
        await self._async_call_action(Service.CREDENTIALS, Credentials.CLEAR, Id=ident)

    async def credentials_set_enabled(self, ident: int, enabled: bool) -> None:
        """Set or clear the enabled state of a service.

        :param ident: the identifier of the credentials
        :param enabled: whether enabled or not
        """
        await self._async_call_action(Service.CREDENTIALS, Credentials.SET_ENABLED, Id=ident, Enabled=enabled)

    async def credentials_get(self, ident: str) -> Mapping[str, Any] | None:
        """Retrieve username, password, status and enabled state for a service.

        :param ident: the identifier for the service
        """
        return await self._async_call_action(Service.CREDENTIALS, Credentials.GET, Id=ident)

    async def credentials_login(self, ident: str) -> Mapping[str, Any] | None:
        """Read a token indicating that a registered user has logged in to a remote service.

        :param ident: the identifier for the service
        """
        return await self._async_call_action(Service.CREDENTIALS, Credentials.LOGIN, Id=ident)

    async def credentials_re_login(self, ident: str, currenttoken: str) -> Mapping[str, Any] | None:
        """Refresh an existing token returned from Login().

        :param ident: the identifier for the service
        :param currenttoken: the current token for the service
        """
        return await self._async_call_action(
            Service.CREDENTIALS, Credentials.RE_LOGIN, Id=ident, CurrentToken=currenttoken
        )

    async def credentials_get_ids(self) -> Mapping[str, Any] | None:
        """Return list of identifiers for services whose credentials can be set."""
        return await self._async_call_action(Service.CREDENTIALS, Credentials.GET_IDS)

    async def credentials_get_public_key(self) -> Mapping[str, Any] | None:
        """Return RSA public key that must be used to encrypt any/all passwords."""
        return await self._async_call_action(Service.CREDENTIALS, Credentials.GET_PUBLIC_KEY)

    async def credentials_get_sequence_number(self) -> Mapping[str, Any] | None:
        """Return Sequence Number."""
        return await self._async_call_action(Service.CREDENTIALS, Credentials.GET_SEQUENCE_NUMBER)

    # endregion

    # region Info Service actions
    async def info_counters(self) -> Mapping[str, Any] | None:
        """Return the counters used to version Track, Details, and Metatext information."""
        return await self._async_call_action(Service.INFO, Info.COUNTERS)

    async def info_track(self) -> Mapping[str, Any] | None:
        """Return current track information concerning the current media."""
        return await self._async_call_action(Service.INFO, Info.TRACK)

    async def info_details(self) -> Mapping[str, Any] | None:
        """Return details concerning the current media."""
        return await self._async_call_action(Service.INFO, Info.DETAILS)

    async def info_metatext(self) -> Mapping[str, Any] | None:
        """Return dynamic textual information concerning the current media."""
        return await self._async_call_action(Service.INFO, Info.METATEXT)

    # endregion

    # region Pins Service actions
    async def pins_get_id_array(self) -> Mapping[str, Any] | None:
        """Get pins id array."""
        return await self._async_call_action(Service.PINS, Pins.GET_ID_ARRAY)

    async def pins_read_list(self, ids: str) -> Mapping[str, Any] | None:
        """Get pins metadata.

        :param ids: space separated string integer array, specifying ids of pins to be read

        :return dict of pins metadata
        """
        return await self._async_call_action(Service.PINS, Pins.READ_LIST, Ids=ids)

    async def pins_get_device_max(self) -> Mapping[str, Any] | None:
        """Get pins max number of devices."""
        return await self._async_call_action(Service.PINS, Pins.GET_DEVICE_MAX)

    async def pins_invoke_index(self, index: int) -> None:
        """Invoke the pin at the specified index in IdArray.

        :param index: the specified index in the IdArray
        """
        await self._async_call_action(Service.PINS, Pins.INVOKE_INDEX, Index = index - 1)

    async def pins_get_modes(self) -> Mapping[str, Any] | None:
        """Get the value for Modes."""
        return await self._async_call_action(Service.PINS, Pins.GET_MODES)

    # endregion

    # region Playlist Service actions
    async def playlist_stop(self) -> None:
        """Stop the current track."""
        await self._async_call_action(Service.PLAYLIST, Playlist.STOP)

    async def playlist_pause(self) -> None:
        """Pause the current track."""
        await self._async_call_action(Service.PLAYLIST, Playlist.PAUSE)

    async def playlist_play(self) -> None:
        """Start playing the track indicated by the Id state variable.."""
        await self._async_call_action(Service.PLAYLIST, Playlist.PLAY)

    async def playlist_next(self) -> None:
        """Start playing the next track in the playlist."""
        await self._async_call_action(Service.PLAYLIST, Playlist.NEXT)

    async def playlist_previous(self) -> None:
        """Start playing the previous track in the playlist."""
        await self._async_call_action(Service.PLAYLIST, Playlist.PREVIOUS)

    async def playlist_set_repeat(self, value: bool) -> None:
        """Enable or disable repeat mode.

        :param value: repeat mode
        """
        await self._async_call_action(Service.PLAYLIST, Playlist.SET_REPEAT, Value=value)

    async def playlist_repeat(self) -> Mapping[str, Any] | None:
        """Return the value of the Repeat state variable."""
        return await self._async_call_action(Service.PLAYLIST, Playlist.REPEAT)

    async def playlist_set_shuffle(self, value: bool) -> None:
        """Enable or disable shuffle mode.

        :param value: shuffle on or off
        """
        await self._async_call_action(Service.PLAYLIST, Playlist.SET_SHUFFLE, Value=value)

    async def playlist_shuffle(self) -> Mapping[str, Any] | None:
        """Return the value of the Shuffle state variable."""
        return await self._async_call_action(Service.PLAYLIST, Playlist.SHUFFLE)

    async def playlist_seek_second_absolute(self, value: int) -> None:
        """Seek to an absolute second within the current track.

        :param value: number of seconds to seek to
        """
        await self._async_call_action(Service.PLAYLIST, Playlist.SEEK_SECOND_ABSOLUTE, Value=value)

    async def playlist_seek_second_relative(self, value: int) -> None:
        """Seek to a relative second within the current track.

        :param value: number of seconds to seek to
        """
        await self._async_call_action(Service.PLAYLIST, Playlist.SEEK_SECOND_RELATIVE, Value=value)

    async def playlist_seek_id(self, value: int) -> None:
        """Switch to the track with the specified id.

        :param value: id
        """
        await self._async_call_action(Service.PLAYLIST, Playlist.SEEK_ID, Value=value)

    async def playlist_seek_index(self, value: int) -> None:
        """Switch to the track with the specified index.

        :param value: index
        """
        await self._async_call_action(Service.PLAYLIST, Playlist.SEEK_INDEX, Value=value)

    async def playlist_transport_state(self) -> Mapping[str, Any] | None:
        """Return the value of the TransportState state variable."""
        return await self._async_call_action(Service.PLAYLIST, Playlist.TRANSPORT_STATE)

    async def playlist_id(self) -> Mapping[str, Any] | None:
        """Return the value of the Id state variable."""
        return await self._async_call_action(Service.PLAYLIST, Playlist.ID)

    async def playlist_read(self, ident: int) -> Mapping[str, Any] | None:
        """Return the uri and metadata for a given track id.

        :param ident: track identifier
        """
        return await self._async_call_action(Service.PLAYLIST, Playlist.READ, Id=ident)

    async def playlist_read_list(self, idlist: str) -> Mapping[str, Any] | None:
        """Return associated uri and metadata for a list of track ids.

        :param idlist: space separated list of track Ids
        """
        return await self._async_call_action(Service.PLAYLIST, Playlist.READ_LIST, IdList=idlist)

    async def playlist_insert(self, afterid: int, uri: str, metadata: str) -> Mapping[str, Any] | None:
        """Add the given uri and metadata as a new track to the playlist.

        :param afterid: insert track after this id; set to 0 to insert at start
        :param uri: uri of the track
        :param metadata: metadata of the track
        """
        return await self._async_call_action(
            Service.PLAYLIST,
            Playlist.INSERT,
            AfterId=afterid,
            Uri=uri,
            Metadata=metadata,
        )

    async def playlist_delete_id(self, value: int) -> None:
        """Perform the action DeleteId.

        :param value: the track id to delete from the playlist
        """
        await self._async_call_action(Service.PLAYLIST, Playlist.DELETE_ID, Value=value)

    async def playlist_delete_all(self) -> None:
        """Delete all tracks from the playlist."""
        await self._async_call_action(Service.PLAYLIST, Playlist.DELETE_ALL)

    async def playlist_tracks_max(self) -> Mapping[str, Any] | None:
        """Return the value of the TracksMax state variable."""
        return await self._async_call_action(Service.PLAYLIST, Playlist.TRACKS_MAX)

    async def playlist_id_array(self) -> Mapping[str, Any] | None:
        """Return the value of the IdArray and Token state variables."""
        return await self._async_call_action(Service.PLAYLIST, Playlist.ID_ARRAY)

    async def playlist_id_array_changed(self, token: int) -> Mapping[str, Any] | None:
        """Check if the token has changed.

        :param token: value of token
        """
        return await self._async_call_action(Service.PLAYLIST, Playlist.ID_ARRAY_CHANGED, Token=token)

    async def playlist_protocol_info(self) -> Mapping[str, Any] | None:
        """Return the value of the ProtocolInfo state variable."""
        return await self._async_call_action(Service.PLAYLIST, Playlist.PROTOCOL_INFO)

    # endregion
    # region Product Service actions

    async def product_attributes(self) -> Mapping[str, Any] | None:
        """Return the value of the Attributes state variable."""
        return await self._async_call_action(Service.PRODUCT, Product.ATTRIBUTES)

    async def product(self) -> Mapping[str, Any] | None:
        """Return the values of the Product state variables.

        :return: ProductRoom, ProductName, ProductInfo, ProductUrl, ProductImageUri
        """
        return await self._async_call_action(Service.PRODUCT, Product.PRODUCT)

    async def product_manufacturer(self) -> Mapping[str, Any] | None:
        """Return the values of the Manufacturer state variables.

        :return: ManufacturerName, ManufacturerInfo, ManufacturerUrl, ManufacturerImageUri
        """
        return await self._async_call_action(Service.PRODUCT, Product.MANUFACTURER)

    async def product_model(self) -> Mapping[str, Any] | None:
        """Return the values of the Model state variables.

        :return: ModelName, ModelInfo, ModelUrl, ModelImageUri
        """
        return await self._async_call_action(Service.PRODUCT, Product.MODEL)

    async def product_set_source_index(self, index: int) -> None:
        """Set the currently active source."""
        await self._async_call_action(Service.PRODUCT, Product.SET_SOURCE_INDEX, Index=index)

    async def product_set_standby(self, standby: bool) -> None:
        """Set the product to standby."""
        await self._async_call_action(Service.PRODUCT, Product.SET_STANDBY, Value=standby)

    async def product_source_count(self) -> Mapping[str, Any] | None:
        """Return the SourceCount state variable."""
        return await self._async_call_action(Service.PRODUCT, Product.SOURCE_COUNT)

    async def product_source(self, index: int) -> Mapping[str, Any] | None:
        """Get the details of the source at index.

        :param index: the source index

        :return: SystemName, Type, Name, Visible
        """
        return await self._async_call_action(Service.PRODUCT, Product.SOURCE, Index=index)

    async def product_source_index(self) -> Mapping[str, Any] | None:
        """Get the current source index."""
        return await self._async_call_action(Service.PRODUCT, Product.SOURCE_INDEX)

    async def product_source_xml(self) -> Mapping[str, Any] | None:
        """Get the product source xml."""
        return await self._async_call_action(Service.PRODUCT, Product.SOURCE_XML)

    async def product_standby(self) -> Mapping[str, Any] | None:
        """Get the product standby status."""
        return await self._async_call_action(Service.PRODUCT, Product.STANDBY)

    # endregion
    # region Radio Service actions
    async def radio_channel(self) -> Mapping[str, Any] | None:
        """Return the values of the Uri and Metadata state variables for the Radio source."""
        return await self._async_call_action(Service.RADIO, Radio.CHANNEL)

    async def radio_pause(self) -> None:
        """Pause any currently playing radio stream."""
        await self._async_call_action(Service.RADIO, Radio.PAUSE)

    async def radio_play(self) -> None:
        """Play the previously selected stream (set via either SetChannel or SetId)."""
        await self._async_call_action(Service.RADIO, Radio.PLAY)

    async def radio_set_channel(self, uri: str, metadata: str) -> None:
        """Set the uri and metadata for a new stream.

        uri: uri for channel
        metadata: metadata for radio channel
            must be valid metadata
        """
        await self._async_call_action(Service.RADIO, Radio.SET_CHANNEL, Uri=uri, Metadata=metadata)

    async def radio_stop(self) -> None:
        """Stop any currently playing radio stream."""
        await self._async_call_action(Service.RADIO, Radio.STOP)

    async def radio_transport_state(self) -> Mapping[str, Any] | None:
        """Return the value of the TransportState state variable."""
        return await self._async_call_action(Service.RADIO, Radio.TRANSPORT_STATE)

    async def radio_id(self) -> Mapping[str, Any] | None:
        """Return the value of the Id state variable."""
        return await self._async_call_action(Service.RADIO, Radio.ID)

    async def radio_set_id(self, value: int, uri: str) -> None:
        """Set the preset id and uri for a new stream.

        :param value: the preset id
        :param uri: the uri of the stream
        """
        await self._async_call_action(Service.RADIO, Radio.SET_ID, Value=value, Uri=uri)

    async def radio_read(self, id: int) -> dict:
        """Given a channel preset Id, return its associated metadata.

        :param id: the preset id
        """
        return await self._async_call_action(Service.RADIO, Radio.READ, Id=id)

    async def radio_read_list(self, idlist: str) -> Mapping[str, Any] | None:
        """Return associated metadata for a list of Ids.

        :param idlist: space separated list of Ids
        """
        return await self._async_call_action(Service.RADIO, Radio.READ_LIST, IdList=idlist)

    async def radio_id_array(self) -> Mapping[str, Any] | None:
        """Return the value of the IdArray and Token state variables."""
        return await self._async_call_action(Service.RADIO, Radio.ID_ARRAY)

    async def radio_id_array_changed(self, token: int) -> Mapping[str, Any] | None:
        """Get the state variables for IdArrayChanged.

        :param token: value of token
        """
        return await self._async_call_action(Service.RADIO, Radio.ID_ARRAY_CHANGED, Token=token)

    async def radio_channels_max(self) -> Mapping[str, Any] | None:
        """Return the value of the ChannelsMax state variable."""
        return await self._async_call_action(Service.RADIO, Radio.CHANNELS_MAX)

    async def radio_protocol_info(self) -> Mapping[str, Any] | None:
        """Return the value of the ProtocolInfo state variable."""
        return await self._async_call_action(Service.RADIO, Radio.PROTOCOL_INFO)

    async def radio_refresh_presets(self) -> None:
        """Perform the action RefreshPresets."""
        await self._async_call_action(Service.RADIO, Radio.REFRESH_PRESETS)

    async def radio_seek_second_absolute(self, value) -> None:
        """Seek to an absolute second within the current stream, if permitted."""
        await self._async_call_action(Service.RADIO, Radio.SEEK_SECOND_ABSOLUTE, Value=value)

    async def radio_seek_second_relative(self, value) -> None:
        """Seek to a relative second within the current stream, if permitted."""
        await self._async_call_action(Service.RADIO, Radio.SEEK_SECOND_RELATIVE, Value=value)

    # endregion

    # region Receiver Service actions
    async def receiver_play(self) -> None:
        """Perform the action Play."""
        await self._async_call_action(Service.RECEIVER, Receiver.PLAY)

    async def receiver_stop(self) -> None:
        """Perform the action Stop."""
        await self._async_call_action(Service.RECEIVER, Receiver.STOP)

    async def receiver_set_sender(self, uri, metadata) -> None:
        """Perform the action SetSender."""
        await self._async_call_action(Service.RECEIVER, Receiver.SET_SENDER, Uri=uri, Metadata=metadata)

    async def receiver_sender(self) -> Mapping[str, Any] | None:
        """Get the state variables for Sender."""
        return await self._async_call_action(Service.RECEIVER, Receiver.SENDER)

    async def receiver_protocol_info(self) -> Mapping[str, Any] | None:
        """Get the state variables for ProtocolInfo."""
        return await self._async_call_action(Service.RECEIVER, Receiver.PROTOCOL_INFO)

    async def receiver_transport_state(self) -> Mapping[str, Any] | None:
        """Get the state variables for TransportState."""
        return await self._async_call_action(Service.RECEIVER, Receiver.TRANSPORT_STATE)

    # endregion

    # region Sender Service actions
    async def sender_presentation_url(self) -> Mapping[str, Any] | None:
        """Return the value of the PresentationUrl state variable."""
        return await self._async_call_action(Service.SENDER, Sender.PRESENTATION_URL)

    async def sender_metadata(self) -> Mapping[str, Any] | None:
        """Return the value of the Metadata state variable."""
        return await self._async_call_action(Service.SENDER, Sender.METADATA)

    async def sender_audio(self) -> Mapping[str, Any] | None:
        """Return the value of the Audio state variable."""
        return await self._async_call_action(Service.SENDER, Sender.AUDIO)

    async def sender_status(self) -> Mapping[str, Any] | None:
        """Return the value of the Status state variable."""
        return await self._async_call_action(Service.SENDER, Sender.STATUS)

    async def sender_status2(self) -> Mapping[str, Any] | None:
        """Return the value of the Status state variable."""
        return await self._async_call_action(Service.SENDER, Sender.STATUS2)

    async def sender_enabled(self) -> Mapping[str, Any] | None:
        """Is the device capable of acting as a Songcast sender."""
        return await self._async_call_action(Service.SENDER, Sender.ENABLED)

    async def sender_attributes(self) -> Mapping[str, Any] | None:
        """Return the value of the Attributes state variable."""
        return await self._async_call_action(Service.SENDER, Sender.ATTRIBUTES)

    # endregion

    # region Time Service actions
    async def time(self) -> Mapping[str, Any] | None:
        """Report time information about progress through a track."""
        return await self._async_call_action(Service.TIME, Time.TIME)

    # endregion
    # region Transport Service actions
    async def transport_pause(self) -> None:
        """Pause the current track or stream."""
        await self._async_call_action(Service.TRANSPORT, Transport.PAUSE)

    async def transport_play(self) -> None:
        """Play the current track or stream."""
        await self._async_call_action(Service.TRANSPORT, Transport.PLAY)

    async def transport_skip_next(self) -> None:
        """Move to the next track or stream."""
        await self._async_call_action(Service.TRANSPORT, Transport.SKIP_NEXT)

    async def transport_skip_previous(self) -> None:
        """Move to the previous track or stream."""
        await self._async_call_action(Service.TRANSPORT, Transport.SKIP_PREVIOUS)

    async def transport_state(self) -> Mapping[str, Any] | None:
        """Return the current value of the TransportState state variable."""
        return await self._async_call_action(Service.TRANSPORT, Transport.TRANSPORT_STATE)

    async def transport_stop(self) -> None:
        """Stop the current track or stream."""
        await self._async_call_action(Service.TRANSPORT, Transport.STOP)

    async def transport_set_repeat(self, repeat: bool) -> None:
        """Set the Repeat state of the device.

        :param repeat: repeat the current playlist
        """
        await self._async_call_action(Service.TRANSPORT, Transport.SET_REPEAT, Repeat=repeat)

    async def transport_set_shuffle(self, shuffle: bool) -> None:
        """Set the Shuffle state of the device.

        :param shuffle: shuffle the current playlist
        """
        await self._async_call_action(Service.TRANSPORT, Transport.SET_SHUFFLE, Shuffle=shuffle)

    async def transport_seek_second_absolute(self, streamid: int, secondabsolute: int) -> None:
        """Seek to an absolute second within the current track or stream, if permitted."""
        await self._async_call_action(
            Service.TRANSPORT,
            Transport.SEEK_SECOND_ABSOLUTE,
            StreamId=streamid,
            SecondAbsolute=secondabsolute,
        )

    async def transport_seek_second_relative(self, streamid: int, secondrelative: int) -> None:
        """Seek to a second relative to the current track or stream position, if permitted."""
        await self._async_call_action(
            Service.TRANSPORT,
            Transport.SEEK_SECOND_RELATIVE,
            StreamId=streamid,
            SecondRelative=secondrelative,
        )

    async def transport_modes(self) -> Mapping[str, Any] | None:
        """Return the value of the Modes state variable."""
        return await self._async_call_action(Service.TRANSPORT, Transport.MODES)

    async def transport_mode_info(self) -> Mapping[str, Any] | None:
        """Return the values of the ModeInfo state variables.

        :return: Mode, CanSkipNext, CanSkipPrev, CanRepeat, CanShuffle
        """
        return await self._async_call_action(Service.TRANSPORT, Transport.MODE_INFO)

    async def transport_stream_info(self) -> Mapping[str, Any] | None:
        """Return the values of the StreamInfo state variables.

        :return: StreamId, Seekable, Pausable
        """
        return await self._async_call_action(Service.TRANSPORT, Transport.STREAM_INFO)

    async def transport_stream_id(self) -> Mapping[str, Any] | None:
        """Return the current value of the StreamId state variable."""
        return await self._async_call_action(Service.TRANSPORT, Transport.STREAM_ID)

    async def transport_repeat(self) -> Mapping[str, Any] | None:
        """Return the current value of the Repeat state variable."""
        return await self._async_call_action(Service.TRANSPORT, Transport.REPEAT)

    async def transport_shuffle(self) -> Mapping[str, Any] | None:
        """Return the current value of the Shuffle state variable."""
        return await self._async_call_action(Service.TRANSPORT, Transport.SHUFFLE)

    async def transport_play_as(self, mode: str, command: str) -> None:
        """Start a new stream playing given a mode and command.

        :param mode: source or group of related sources
        :param command: mode specific command
        """
        return await self._async_call_action(Service.TRANSPORT, Transport.PLAY_AS, Mode=mode, Command=command)

    # endregion
    # region Update Service actions
    async def update_apply(self) -> None:
        """Apply a software update."""
        await self._async_call_action(Service.UPDATE, Update.APPLY)

    async def update_check_now(self) -> Mapping[str, Any] | None:
        """Check the current status of the software."""
        return await self._async_call_action(Service.UPDATE, Update.CHECK_NOW)

    async def update_get_software_status(self) -> Mapping[str, Any] | None:
        """Return the current status of the software."""
        return await self._async_call_action(Service.UPDATE, Update.GET_SOFTWARE_STATUS)

    # endregion
    # region Volume Service actions
    async def volume_set(self, volume_level: int) -> None:
        """Set the volume level.

        :param volume_level: the absolute value of the volume
        """
        await self._async_call_action(Service.VOLUME, Volume.SET_VOLUME, Value=volume_level)

    async def volume_set_mute(self, is_muted: bool) -> None:
        """Set the volume mute state.

        :param is_muted: is the volume muted or not
        """
        # do not unmute by inadvertently sending a 'Falsy'
        is_muted = _strict_false(is_muted)
        # is_muted = bool(is_muted) # it behaves this way anyway
        await self._async_call_action(Service.VOLUME, Volume.SET_MUTE, Value=is_muted)

    async def volume_inc(self) -> None:
        """Increase the volume level by one."""
        await self._async_call_action(Service.VOLUME, Volume.VOLUME_INC)

    async def volume_dec(self) -> None:
        """Decrease the volume level by one."""
        await self._async_call_action(Service.VOLUME, Volume.VOLUME_DEC)

    # these actions return the values of state variables having been polled
    async def volume_volume(self) -> Mapping[str, Any] | None:
        """Return the value of the current volume level."""
        return await self._async_call_action(Service.VOLUME, Volume.VOLUME)

    async def volume_mute(self) -> Mapping[str, Any] | None:
        """Return the value of the current volume mute state."""
        return await self._async_call_action(Service.VOLUME, Volume.MUTE)

    async def volume_characteristics(self) -> Mapping[str, Any] | None:
        """Return the value of the Characteristics state variables.

        :return: VolumeMax, VolumeUnity, VolumeSteps, VolumeMilliDbPerStep, BalanceMax, FadeMax
        """
        return await self._async_call_action(Service.VOLUME, Volume.CHARACTERISTICS)

    async def volume_set_no_unmute(self, value: int) -> None:
        """Set the absolute volume level without un-muting.

        :param value: the absolute volume level to set
        """
        await self._async_call_action(Service.VOLUME, Volume.SET_VOLUME_NO_UNMUTE, Value=value)

    async def volume_inc_no_unmute(self) -> None:
        """Increase the volume level by one without un-muting."""
        await self._async_call_action(Service.VOLUME, Volume.VOLUME_INC_NO_UNMUTE)

    async def volume_dec_no_unmute(self) -> None:
        """Decrease the volume level by one without un-muting."""
        await self._async_call_action(Service.VOLUME, Volume.VOLUME_DEC_NO_UNMUTE)

    async def volume_set_balance(self, value: int) -> None:
        """Set the volume left-right balance.

        :param value: the balance level to set
        """
        await self._async_call_action(Service.VOLUME, Volume.SET_BALANCE, Value=value)

    async def volume_balance_inc(self) -> None:
        """Increase the balance level by one."""
        await self._async_call_action(Service.VOLUME, Volume.BALANCE_INC)

    async def volume_balance_dec(self) -> None:
        """Decrease the balance level by one."""
        await self._async_call_action(Service.VOLUME, Volume.BALANCE_DEC)

    async def volume_balance(self) -> Mapping[str, Any] | None:
        """Return the value of the Balance state variable."""
        return await self._async_call_action(Service.VOLUME, Volume.BALANCE)

    async def volume_set_fade(self, value: int) -> None:
        """Set the value of Fade (front-rear) balance.

        :param value: the Fade value to set
        """
        await self._async_call_action(Service.VOLUME, Volume.SET_FADE, Value=value)

    async def volume_fade_inc(self) -> None:
        """Increase the value of Fade (front-rear) balance by one."""
        await self._async_call_action(Service.VOLUME, Volume.FADE_INC)

    async def volume_fade_dec(self) -> None:
        """Decrease the value of Fade (front-rear) balance by one."""
        await self._async_call_action(Service.VOLUME, Volume.FADE_DEC)

    async def volume_fade(self) -> Mapping[str, Any] | None:
        """Return the value of the Fade state variable."""
        return await self._async_call_action(Service.VOLUME, Volume.FADE)

    async def volume_limit(self) -> Mapping[str, Any] | None:
        """Return value of the VolumeLimit state variable."""
        return await self._async_call_action(Service.VOLUME, Volume.VOLUME_LIMIT)

    async def volume_unity_gain(self) -> Mapping[str, Any] | None:
        """Return value of the UnityGain state variable."""
        return await self._async_call_action(Service.VOLUME, Volume.UNITY_GAIN)

    async def volume_offset(self, channel: str) -> Mapping[str, Any] | None:
        """Return value of the VolumeOffset state variable.

        :param channel: the channel for which to return the volume offset
        """
        return await self._async_call_action(Service.VOLUME, Volume.VOLUME_OFFSET, Channel=channel)

    async def volume_set_offset(self, channel: str, volumeoffsetbinarymillidb: int) -> None:
        """Set the value of the VolumeOffset state variable.

        :param channel:
        :param volumeoffsetbinarymillidb: the volume offset in binary milli decibels (mibi dB)
        """
        await self._async_call_action(
            Service.VOLUME,
            Volume.SET_VOLUME_OFFSET,
            Channel=channel,
            VolumeOffsetBinaryMilliDb=volumeoffsetbinarymillidb,
        )

    async def volume_trim(self, channel: str) -> Mapping[str, Any] | None:
        """Get the state variables for Trim.

        :param channel: the device channel to report on
        """
        return await self._async_call_action(Service.VOLUME, Volume.TRIM, Channel=channel)

    async def volume_set_trim(self, channel: str, trimbinarymillidb: int) -> None:
        """Trim the Volume of the channel.

        :param channel: the device channel
        :param trimbinarymillidb: the trim value in binary milli decibels (mibi dB)
        """
        await self._async_call_action(
            Service.VOLUME,
            Volume.SET_TRIM,
            Channel=channel,
            TrimBinaryMilliDb=trimbinarymillidb,
        )

    # endregion

    # region syntactic helpers
    async def active_source_index(self) -> int | None:
        """Get the active source index."""
        return int((await self.product_source_index())["Value"])

    async def active_source_name(self) -> str:
        """Get the active source name."""
        return (await self.product_source(await self.active_source_index()))["Name"] or "N/A"

    async def sources(self):
        """Get list of active sources."""
        result = (await self.product_source_xml())["Value"]
        sources_list_xml = ET.fromstring(result)
        sources = []
        index = 0
        for source_xml in sources_list_xml:
            visible = source_xml.find("Visible").text == "true"
            if visible:
                sources.append(
                    {
                        "Index": index,
                        "Name": source_xml.find("Name").text,
                        "Type": source_xml.find("Type").text,
                    }
                )
            index = index + 1

        return sources

    @property
    async def is_standby(self) -> str | None:
        """Get standby status."""
        return (await self.product_standby())["Value"]

    @property
    async def is_muted(self) -> bool | None:
        """Get mute status."""
        return (await self.volume_mute())["Value"]

    @property
    async def volume(self) -> int | None:
        """Return the Volume level."""
        return await self._state_var_value(Service.VOLUME, VolumeState.VOLUME)

    @property
    async def product_room(self) -> str | None:
        """Return the room where product is located."""
        return await self._state_var_value(Service.PRODUCT, ProductState.PRODUCT_ROOM)

    @property
    async def product_name(self) -> str | None:
        """Return the name of product."""
        return await self._state_var_value(Service.PRODUCT, ProductState.PRODUCT_NAME)

    async def play(self) -> None:
        """Play."""
        await self.transport_play()

    async def stop(self) -> None:
        """Stop."""
        await self.transport_stop()

    async def pause(self) -> None:
        """Pause."""
        await self.transport_pause()

    # endregion

    # region other

    async def _state_var_value(self, service_name, state_variable_name, **kwargs) -> bool | dict | int | str | None:
        """Return value of state variable."""

        state_var = self._state_variable(service_name, state_variable_name)
        if state_var is None:  # state variable not listed in Service XML description
            return None

        if state_var.value is None:  # state variable not populated
            action = _action_for_state_var(service_name, state_var.name)
            await self._async_poll_state_variables(service_name, action)
            state_var = self._state_variable(service_name, state_variable_name)
            if state_var.value is None:

        return state_var.value

    async def _async_call_action(self, service_name: str, action_name: str, **kwargs: Any) -> dict | None:
        _LOGGER.debug("Missing State Variable %s:%s", service_name, state_variable_name)
        """Call service action with arguments."""

        service = self._service(service_name)
        if not service:
            _LOGGER.warning("%s device does not offer service", service_name)
            return None

        if not service.has_action(action_name):
            _LOGGER.warning("%s service does not offer action %s", service_name, action_name)
            return None
        action = service.action(action_name)
        result = await action.async_call(**kwargs)
        return result if result else None

    async def playlist_last_id(self) -> int:
        """Return the last id of the playlist."""

        id_array = (await self.playlist_id_array())["Array"]
        decoded = _decode_id_array(self, id_array)
        if len(decoded) > 0:
            last_id = decoded[-1]
        else:
            last_id = 0
        return last_id

    async def pins_set_device(self, pin_metadata: dict):
        """Set Pins service device using single metadata dictionary.

        :param pin_metadata: dictionary containing necessary metadata
        """

        await self._async_call_action(
            Service.PINS,
            Pins.SET_DEVICE,
            Index=(pin_metadata["id"]),
            Mode=pin_metadata["mode"],
            Type=pin_metadata["type"],
            Uri=pin_metadata["uri"],
            Title=pin_metadata["title"],
            Description=pin_metadata["description"],
            ArtworkUri=pin_metadata["artworkUri"],
            Shuffle=pin_metadata["shuffle"],
        )


# endregion


# region functions independent of class
def _action_for_state_var(service_name: str, state_variable_name: str) -> str:
    """Lookup action corresponding to state variable."""

    info_sv_action = {
        "BitDepth": "Details",
        "BitRate": "Details",
        "CodecName": "Details",
        "DetailsCount": "Counters",
        "Duration": "Details",
        "Lossless": "Details",
        "Metadata": "Track",
        "MetatextCount": "Counters",
        "SampleRate": "Details",
        "TrackCount": "Counters",
        "Uri": "Track",
    }

    pins_sv_action = {
        "A_ARG_TYPE_ReadList_List": "ReadList",
        "AccountMax": "GetAccountMax",
        "CloudConnected": "GetCloudConnected",
        "DeviceMax": "GetDeviceMax",
        "IdArray": "GetIdArray",
        "Modes": "GetModes",
    }

    playlist_sv_action = {
        "A_ARG_TYPE_IdArray_Token": "IdArray",
        "A_ARG_TYPE_IdArrayChanged_Value": "IdArrayChanged",
        "A_ARG_TYPE_Read_Metadata": "Read",
        "A_ARG_TYPE_Read_Uri": "Read",
        "A_ARG_TYPE_ReadList_TrackList": "ReadList",
        "Id": "Insert",
    }

    product_sv_action = {
        "A_ARG_TYPE_Source_Name": "Source",
        "A_ARG_TYPE_Source_SystemName": "Source",
        "A_ARG_TYPE_Source_Type": "Source",
        "A_ARG_TYPE_Source_Visible": "Source",
        "A_ARG_TYPE_SourceXmlChangeCount_Value": "SourceXmlChangeCount",
        "ManufacturerImageUri": "Manufacturer",
        "ManufacturerInfo": "Manufacturer",
        "ManufacturerName": "Manufacturer",
        "ManufacturerUrl": "Manufacturer",
        "ModelImageUri": "Model",
        "ModelInfo": "Model",
        "ModelName": "Model",
        "ModelUrl": "Model",
        "ProductImageHiresUri": "Product",
        "ProductImageUri": "GetImageUri",
        "ProductInfo": "Product",
        "ProductName": "Product",
        "ProductRoom": "Product",
        "ProductUrl": "Product",
    }

    radio_sv_action = {
        "A_ARG_TYPE_IdArray_Token": "IdArray",
        "A_ARG_TYPE_IdArrayChanged_Value": "IdArrayChanged",
        "A_ARG_TYPE_ReadList_ChannelList": "ReadList",
        "Metadata": "Channel",
        "Uri": "Channel",
    }

    volume_sv_action = {
        "A_ARG_TYPE_Trim_TrimBinaryMilliDb": "Trim",
        "A_ARG_TYPE_VolumeOffset_VolumeOffsetBinaryMilliDb": "VolumeOffset",
        "BalanceMax": "Characteristics",
        "FadeMax": "Characteristics",
        "VolumeMax": "Characteristics",
        "VolumeMilliDbPerStep": "Characteristics",
        "VolumeSteps": "Characteristics",
        "VolumeUnity": "Characteristics",
    }

    transport_sv_action = {
        "CanPause": "StreamInfo",
        "CanRepeat": "ModeInfo",
        "CanSeek": "StreamInfo",
        "CanShuffle": "ModeInfo",
        "CanSkipNext": "ModeInfo",
        "CanSkipPrevious": "ModeInfo",
        "StreamId": "StreamInfo",
    }

    match service_name:
        case Service.INFO:
            mapping = info_sv_action
        case Service.PINS:
            mapping = pins_sv_action
        case Service.PLAYLIST:
            mapping = playlist_sv_action
        case Service.PRODUCT:
            mapping = product_sv_action
        case Service.RADIO:
            mapping = radio_sv_action
        case Service.TRANSPORT:
            mapping = transport_sv_action
        case Service.VOLUME:
            mapping = volume_sv_action
        case _:
            mapping = {}

    if state_variable_name in mapping:
        return mapping[state_variable_name]
    return state_variable_name


def _strict_false(val: Any) -> bool:
    """Only False if val is explicitly False, "False" or 0."""

    if val is None:
        return True  # counter-intuitive but insist on False means False
    match val:
        case False | "False" | 0:
            return False
        case _:
            return True


def _list_to_string(list_int: list) -> str:
    """Convert list to space separated string."""
    return " ".join(map(str, filter(lambda x: x > 0, list_int)))


def _decode_id_array(b64_id_array: str) -> list:
    """Convert base64 encoded list to list of integers."""

    encoded_as_bytes = b64_id_array.encode('utf-8')
    try:
        decoded = base64.b64decode(encoded_as_bytes, validate=True)
    except binascii.Error:
        raise ValueError("Invalid base64 encoding.")

    array_int = list(struct.unpack(">" + "I" * (len(decoded) // 4), decoded))
    # quick sanity check on first 4 bytes
    if not int.from_bytes(decoded[0:4], "big") < 1000:
        array_int = []

    return array_int
# endregion
