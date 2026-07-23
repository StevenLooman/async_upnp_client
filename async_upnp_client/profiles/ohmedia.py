"""async_upnp_client profile for OpenHome Media players.

This profile has many convenience methods for invoking an action from an OpenHome Media service
Not all devices will offer all services and actions. If a service or action is not available
then an error will be raised.
"""

# pylint: disable=too-many-public-methods,too-many-lines
import base64
import binascii
import logging
import struct
from enum import Enum  # py310 replace str, Enum with StrEnum when Python 3.10 becomes end-of-life
from typing import Any, Mapping, Sequence

import defusedxml.ElementTree as DET

from async_upnp_client.exceptions import UpnpError
from async_upnp_client.profiles.profile import UpnpProfileDevice

_LOGGER = logging.getLogger(__name__)


# region Service and other enums
class Service(str, Enum):
    """Linn/OpenHome Network Service Identifiers.

    The Service Identifier from the ServiceId
    This assumes no collisions if domain namespace is ignored
    """

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


class ServiceId(str, Enum):
    """Linn/OpenHome Network Service Ids.

    A service ID uniquely identifies a service instance within a device.
    It follows a URI format of urn:<domain-namespace>:serviceId:<ServiceIdentifier>
    """

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


class ProductSourceType(str, Enum):
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
# These Enums are intended to cover the complete specification
# Only a subset of actions which are deemed useful at present are implemented
class Credentials(str, Enum):
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


class Info(str, Enum):
    """Actions for Info Service."""

    COUNTERS = "Counters"
    TRACK = "Track"
    DETAILS = "Details"
    METATEXT = "Metatext"


class Pins(str, Enum):
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


class Playlist(str, Enum):
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


class Product(str, Enum):
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
    SET_SOURCE_BY_SYSTEM_NAME = "SetSourceBySystemName"
    SOURCE = "Source"
    ATTRIBUTES = "Attributes"
    SOURCE_XML_CHANGE_COUNT = "SourceXmlChangeCount"
    GET_IMAGE_URI = "GetImageUri"


class Radio(str, Enum):
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


class Receiver(str, Enum):
    """Actions for Receiver Service."""

    PLAY = "Play"
    STOP = "Stop"
    SET_SENDER = "SetSender"
    SENDER = "Sender"
    PROTOCOL_INFO = "ProtocolInfo"
    TRANSPORT_STATE = "TransportState"


class Sender(str, Enum):
    """Actions for Sender Service."""

    PRESENTATION_URL = "PresentationUrl"
    METADATA = "Metadata"
    AUDIO = "Audio"
    STATUS = "Status"
    STATUS2 = "Status2"
    ENABLED = "Enabled"
    ATTRIBUTES = "Attributes"


class Time(str, Enum):
    """Actions for Time Service."""

    TIME = "Time"


class Transport(str, Enum):
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


class Update(str, Enum):
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


class Volume(str, Enum):
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
class CredentialsState(str, Enum):
    """State variable names for Credentials service."""

    IDS = "Ids"
    PUBLIC_KEY = "PublicKey"
    SEQUENCE_NUMBER = "SequenceNumber"


class InfoState(str, Enum):
    """State variable names for Info service."""

    BIT_DEPTH = "BitDepth"
    BIT_RATE = "BitRate"
    CODEC_NAME = "CodecName"
    DETAILS_COUNT = "DetailsCount"
    DURATION = "Duration"
    LOSSLESS = "Lossless"
    METADATA = "Metadata"
    METATEXT = "Metatext"
    METATEXT_COUNT = "MetatextCount"
    SAMPLE_RATE = "SampleRate"
    TRACK_COUNT = "TrackCount"
    URI = "Uri"


class PinsState(str, Enum):
    """State variable names for Pins service."""

    ACCOUNT_MAX = "AccountMax"
    CLOUD_CONNECTED = "CloudConnected"
    DEVICE_MAX = "DeviceMax"
    ID_ARRAY = "IdArray"
    MODES = "Modes"


class PlaylistState(str, Enum):
    """State variable names for Playlist service."""

    ID = "Id"
    ID_ARRAY = "IdArray"
    PROTOCOL_INFO = "ProtocolInfo"
    REPEAT = "Repeat"
    SHUFFLE = "Shuffle"
    TRACKS_MAX = "TracksMax"
    TRANSPORT_STATE = "TransportState"


class PlaylistStateAllowedValues(str, Enum):
    """Allowed values for Playlist service."""

    BUFFERING = "Buffering"
    PAUSED = "Paused"
    PLAYING = "Playing"
    STOPPED = "Stopped"


class ProductState(str, Enum):
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


class RadioState(str, Enum):
    """State variable names for Radio service."""

    CHANNELS_MAX = "ChannelsMax"
    ID = "Id"
    ID_ARRAY = "IdArray"
    PROTOCOL_INFO = "ProtocolInfo"
    METADATA = "Metadata"
    URI = "Uri"
    TRANSPORT_STATE = "TransportState"


class ReceiverState(str, Enum):
    """State variable names for Receiver service."""

    PROTOCOL_INFO = "ProtocolInfo"
    METADATA = "Receiver_Metadata"
    URI = "Receiver_Uri"
    TRANSPORT_STATE = "TransportState"


class SenderState(str, Enum):
    """State variable names for Sender service."""

    ATTRIBUTES = "Attributes"
    AUDIO = "Audio"
    ENABLED = "Enabled"
    PRESENTATION_URL = "PresentationUrl"
    METADATA = "Metadata"
    STATUS = "Status"
    STATUS2 = "Status2"


class TimeState(str, Enum):
    """State variable names for Time service."""

    DURATION = "Duration"
    SECONDS = "Seconds"
    TRACK_COUNT = "TrackCount"


class TransportState(str, Enum):
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


class TransportStateAllowedValues(str, Enum):
    """Allowed values for Transport service."""

    BUFFERING = "Buffering"
    PAUSED = "Paused"
    PLAYING = "Playing"
    STOPPED = "Stopped"
    WAITING = "Waiting"


class UpdateState(str, Enum):
    """State variable names for Update service."""

    EXECUTOR_STATUS = "ExecutorStatus"
    JOB_STATUS = "JobStatus"
    RECOVER_SUPPORTED = "RecoverSupported"
    SOFTWARE_STATUS = "SoftwareStatus"


class VolumeState(str, Enum):
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

    # region enums and constants
    DEVICE_TYPES = [
        "urn:av-openhome-org:device:Source:1",
        "urn:linn-co-uk:device:Source:1",
    ]

    # Product is the only service which must be available to be OpenHome Media compliant
    SERVICE_IDS = frozenset(("urn:av-openhome-org:serviceId:Product",))

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

    # region Credentials Service actions
    async def async_credentials_set(self, ident: str, username: str, password: str) -> None:
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

    async def async_credentials_clear(self, ident: str) -> None:
        """Remove both username and password for a given service.

        :param ident: the identifier for the service
        """
        await self._async_call_action(Service.CREDENTIALS, Credentials.CLEAR, Id=ident)

    async def async_credentials_set_enabled(self, ident: str, enabled: bool) -> None:
        """Set or clear the enabled state of a service.

        :param ident: the identifier of the credentials
        :param enabled: whether enabled or not
        """
        await self._async_call_action(Service.CREDENTIALS, Credentials.SET_ENABLED, Id=ident, Enabled=enabled)

    async def async_credentials_get(self, ident: str) -> Mapping[str, str | bool]:
        """Retrieve username, password, status and enabled state for a service.

        :param ident: the identifier for the service
        """
        return await self._async_call_action(Service.CREDENTIALS, Credentials.GET, Id=ident)

    async def async_credentials_login(self, ident: str) -> Mapping[str, Any]:
        """Read a token indicating that a registered user has logged in to a remote service.

        :param ident: the identifier for the service
        """
        return await self._async_call_action(Service.CREDENTIALS, Credentials.LOGIN, Id=ident)

    async def async_credentials_re_login(self, ident: str, currenttoken: str) -> Mapping[str, Any]:
        """Refresh an existing token returned from Login().

        :param ident: the identifier for the service
        :param currenttoken: the current token for the service
        """
        return await self._async_call_action(
            Service.CREDENTIALS,
            Credentials.RE_LOGIN,
            Id=ident,
            CurrentToken=currenttoken,
        )

    async def async_credentials_get_ids(self) -> Mapping[str, str]:
        """Return list of identifiers for services whose credentials can be set."""
        return await self._async_call_action(Service.CREDENTIALS, Credentials.GET_IDS)

    async def async_credentials_get_public_key(self) -> Mapping[str, str]:
        """Return RSA public key that must be used to encrypt any/all passwords."""
        return await self._async_call_action(Service.CREDENTIALS, Credentials.GET_PUBLIC_KEY)

    async def async_credentials_get_sequence_number(self) -> Mapping[str, int]:
        """Return Sequence Number."""
        return await self._async_call_action(Service.CREDENTIALS, Credentials.GET_SEQUENCE_NUMBER)

    # endregion
    # region Info Service actions
    async def async_info_counters(self) -> Mapping[str, int]:
        """Return the counters used to version Track, Details, and Metatext information."""
        return await self._async_call_action(Service.INFO, Info.COUNTERS)

    async def async_info_track(self) -> Mapping[str, str]:
        """Return current track information concerning the current media."""
        return await self._async_call_action(Service.INFO, Info.TRACK)

    async def async_info_details(self) -> Mapping[str, int | bool | str]:
        """Return details concerning the current media."""
        return await self._async_call_action(Service.INFO, Info.DETAILS)

    async def async_info_metatext(self) -> Mapping[str, str]:
        """Return dynamic textual information concerning the current media."""
        return await self._async_call_action(Service.INFO, Info.METATEXT)

    # endregion
    # region Pins Service actions
    async def async_pins_get_device_max(self) -> Mapping[str, int]:
        """Return the value of the DeviceMax state variable.

        :return: DeviceMax
        DeviceMax is the maximum number of device-specific pins supported
        """
        return await self._async_call_action(Service.PINS, Pins.GET_DEVICE_MAX)

    async def async_pins_get_account_max(self) -> Mapping[str, int]:
        """Return the value of the AccountMax state variable.

        :return: AccountMax
        AccountMax is the maximum number of account-wide pins supported
        """
        return await self._async_call_action(Service.PINS, Pins.GET_ACCOUNT_MAX)

    async def async_pins_get_modes(self) -> Mapping[str, str]:
        """Return the value of the Modes state variable.

        :return: Modes
        Modes is a JSON array of strings identifying the different styles of pins supported
        """
        return await self._async_call_action(Service.PINS, Pins.GET_MODES)

    async def async_pins_get_id_array(self) -> Mapping[str, str]:
        """Get pins id array.

        :return: IdArray
        """
        return await self._async_call_action(Service.PINS, Pins.GET_ID_ARRAY)

    async def async_pins_read_list(self, ids: str) -> Mapping[str, str]:
        """Get pins metadata.

        :param ids: string representation of integer array of ids of pins

        :return: List
        """
        return await self._async_call_action(Service.PINS, Pins.READ_LIST, Ids=ids)

    async def async_pins_invoke_uri(self, mode: str, pin_type: str, uri: str, shuffle: bool) -> None:
        """Invoke a pin using data (mode, type, uri, shuffle) from a control point.

        :param mode: one of the modes available from GetModes
        :param type: the type of the uri
        :param uri: the uri of the stream/track
        :param shuffle: whether to shuffle or not

        """
        await self._async_call_action(
            Service.PINS,
            Pins.INVOKE_URI,
            Mode=mode,
            Type=pin_type,
            Uri=uri,
            Shuffle=shuffle,
        )

    async def async_pins_invoke_id(self, ident: int) -> None:
        """Invoke the pin with identifier ident.

        :param ident: the identifier of the pin in the IdArray
        """
        await self._async_call_action(Service.PINS, Pins.INVOKE_ID, Id=ident)

    async def async_pins_invoke_index(self, index: int) -> None:
        """Invoke the pin at the specified index in IdArray.

        :param index: the index of the pin to invoke

        Note that index expected here corresponds to the 1-based index as presented by the Linn app
        This normally ranges from 1 to DeviceMax corresponding to a Python 0-based array index from 0 to DeviceMax-1
        """
        await self._async_call_action(Service.PINS, Pins.INVOKE_INDEX, Index=index - 1)

    # pylint: disable=too-many-arguments,too-many-positional-arguments
    async def async_pins_set_device(
        self,
        index: int,
        mode: str,
        pin_type: str,
        uri: str,
        title: str,
        description: str,
        artworkuri: str,
        shuffle: bool,
    ) -> None:
        """Set a device pin, specifying the parameters of the device pin."""
        await self._async_call_action(
            Service.PINS,
            Pins.SET_DEVICE,
            Index=index,
            Mode=mode,
            Type=pin_type,
            Uri=uri,
            Title=title,
            Description=description,
            ArtworkUri=artworkuri,
            Shuffle=shuffle,
        )

    async def async_pins_set_account(
        self,
        index: int,
        mode: str,
        pin_type: str,
        uri: str,
        title: str,
        description: str,
        artworkuri: str,
        shuffle: bool,
    ) -> None:
        """Set an account pin, specifying the parameters of the account pin."""
        await self._async_call_action(
            Service.PINS,
            Pins.SET_ACCOUNT,
            Index=index,
            Mode=mode,
            Type=pin_type,
            Uri=uri,
            Title=title,
            Description=description,
            ArtworkUri=artworkuri,
            Shuffle=shuffle,
        )

    async def async_pins_clear(self, ident: int) -> None:
        """Clear any content in the pin with the specified identifier.

        :param ident: the identifier of the pin to clear
        """
        await self._async_call_action(Service.PINS, Pins.CLEAR, Id=ident)

    async def async_pins_swap(self, index1: int, index2: int) -> None:
        """Swap contents of the 2 pins at the specified indices.

        :param index1: the index to swap
        :param index2: the index to swap
        """
        await self._async_call_action(Service.PINS, Pins.SWAP, Index1=index1, Index2=index2)

    # endregion
    # region Playlist Service actions
    async def async_playlist_stop(self) -> None:
        """Stop the current track."""
        await self._async_call_action(Service.PLAYLIST, Playlist.STOP)

    async def async_playlist_pause(self) -> None:
        """Pause the current track."""
        await self._async_call_action(Service.PLAYLIST, Playlist.PAUSE)

    async def async_playlist_play(self) -> None:
        """Start playing the track indicated by the Id state variable."""
        await self._async_call_action(Service.PLAYLIST, Playlist.PLAY)

    async def async_playlist_next(self) -> None:
        """Start playing the next track in the playlist."""
        await self._async_call_action(Service.PLAYLIST, Playlist.NEXT)

    async def async_playlist_previous(self) -> None:
        """Start playing the previous track in the playlist."""
        await self._async_call_action(Service.PLAYLIST, Playlist.PREVIOUS)

    async def async_playlist_set_repeat(self, value: bool) -> None:
        """Enable or disable repeat mode.

        :param value: repeat mode
        """
        await self._async_call_action(Service.PLAYLIST, Playlist.SET_REPEAT, Value=value)

    async def async_playlist_repeat(self) -> Mapping[str, bool]:
        """Return the value of the Repeat state variable."""
        return await self._async_call_action(Service.PLAYLIST, Playlist.REPEAT)

    async def async_playlist_set_shuffle(self, value: bool) -> None:
        """Enable or disable shuffle mode.

        :param value: shuffle on or off
        """
        await self._async_call_action(Service.PLAYLIST, Playlist.SET_SHUFFLE, Value=value)

    async def async_playlist_shuffle(self) -> Mapping[str, bool] | None:
        """Return the value of the Shuffle state variable."""
        return await self._async_call_action(Service.PLAYLIST, Playlist.SHUFFLE)

    async def async_playlist_seek_second_absolute(self, value: int) -> None:
        """Seek to an absolute second within the current track.

        :param value: number of seconds to seek to
        """
        await self._async_call_action(Service.PLAYLIST, Playlist.SEEK_SECOND_ABSOLUTE, Value=value)

    async def async_playlist_seek_second_relative(self, value: int) -> None:
        """Seek to a relative second within the current track.

        :param value: number of seconds to seek to
        """
        await self._async_call_action(Service.PLAYLIST, Playlist.SEEK_SECOND_RELATIVE, Value=value)

    async def async_playlist_seek_id(self, value: int) -> None:
        """Switch to the track with the specified id.

        :param value: id
        """
        await self._async_call_action(Service.PLAYLIST, Playlist.SEEK_ID, Value=value)

    async def async_playlist_seek_index(self, value: int) -> None:
        """Switch to the track with the specified index.

        :param value: index
        """
        await self._async_call_action(Service.PLAYLIST, Playlist.SEEK_INDEX, Value=value)

    async def async_playlist_transport_state(self) -> Mapping[str, str]:
        """Return the value of the TransportState state variable."""
        return await self._async_call_action(Service.PLAYLIST, Playlist.TRANSPORT_STATE)

    async def async_playlist_id(self) -> Mapping[str, int]:
        """Return the value of the Id state variable."""
        return await self._async_call_action(Service.PLAYLIST, Playlist.ID)

    async def async_playlist_read(self, ident: int) -> Mapping[str, str]:
        """Return the uri and metadata for a given track id.

        :param ident: track identifier
        """
        return await self._async_call_action(Service.PLAYLIST, Playlist.READ, Id=ident)

    async def async_playlist_read_list(self, idlist: str) -> Mapping[str, str]:
        """Return associated uri and metadata for a list of track ids.

        :param idlist: space separated list of track Ids
        """
        return await self._async_call_action(Service.PLAYLIST, Playlist.READ_LIST, IdList=idlist)

    async def async_playlist_insert(self, afterid: int, uri: str, metadata: str) -> Mapping[str, int]:
        """Add the given uri and metadata as a new track to the playlist.

        :param afterid: insert track after this identifier; set to 0 to insert at start
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

    async def async_playlist_delete_id(self, value: int) -> None:
        """Perform the action DeleteId.

        :param value: the track id to delete from the playlist
        """
        await self._async_call_action(Service.PLAYLIST, Playlist.DELETE_ID, Value=value)

    async def async_playlist_delete_all(self) -> None:
        """Delete all tracks from the playlist."""
        await self._async_call_action(Service.PLAYLIST, Playlist.DELETE_ALL)

    async def async_playlist_tracks_max(self) -> Mapping[str, int]:
        """Return the value of the TracksMax state variable."""
        return await self._async_call_action(Service.PLAYLIST, Playlist.TRACKS_MAX)

    async def async_playlist_id_array(self) -> Mapping[str, str]:
        """Return the value of the IdArray and Token state variables."""
        return await self._async_call_action(Service.PLAYLIST, Playlist.ID_ARRAY)

    async def async_playlist_id_array_changed(self, token: int) -> Mapping[str, bool]:
        """Check if the token has changed.

        :param token: value of token
        """
        return await self._async_call_action(Service.PLAYLIST, Playlist.ID_ARRAY_CHANGED, Token=token)

    async def async_playlist_protocol_info(self) -> Mapping[str, str]:
        """Return the value of the ProtocolInfo state variable."""
        return await self._async_call_action(Service.PLAYLIST, Playlist.PROTOCOL_INFO)

    # endregion
    # region Product Service actions

    async def async_product_attributes(self) -> Mapping[str, str]:
        """Return the value of the Attributes state variable."""
        return await self._async_call_action(Service.PRODUCT, Product.ATTRIBUTES)

    async def async_product(self) -> Mapping[str, str]:
        """Return the values of the Product state variables.

        :return: ProductRoom, ProductName, ProductInfo, ProductUrl, ProductImageUri
        """
        return await self._async_call_action(Service.PRODUCT, Product.PRODUCT)

    async def async_product_manufacturer(self) -> Mapping[str, str]:
        """Return the values of the Manufacturer state variables.

        :return: ManufacturerName, ManufacturerInfo, ManufacturerUrl, ManufacturerImageUri
        """
        return await self._async_call_action(Service.PRODUCT, Product.MANUFACTURER)

    async def async_product_model(self) -> Mapping[str, str]:
        """Return the values of the Model state variables.

        :return: ModelName, ModelInfo, ModelUrl, ModelImageUri
        """
        return await self._async_call_action(Service.PRODUCT, Product.MODEL)

    async def async_product_set_source_index(self, index: int) -> None:
        """Set the currently active source."""
        await self._async_call_action(Service.PRODUCT, Product.SET_SOURCE_INDEX, Value=index)

    async def async_product_set_standby(self, standby: bool) -> None:
        """Set the product to standby."""
        await self._async_call_action(Service.PRODUCT, Product.SET_STANDBY, Value=standby)

    async def async_product_source_count(self) -> Mapping[str, int]:
        """Return the SourceCount state variable."""
        return await self._async_call_action(Service.PRODUCT, Product.SOURCE_COUNT)

    async def async_product_source(self, index: int) -> Mapping[str, str | bool]:
        """Get the details of the source at index.

        :param index: the source index

        :return: SystemName, Type, Name, Visible
        """
        return await self._async_call_action(Service.PRODUCT, Product.SOURCE, Index=index)

    async def async_product_source_index(self) -> Mapping[str, int]:
        """Get the current source index."""
        return await self._async_call_action(Service.PRODUCT, Product.SOURCE_INDEX)

    async def async_product_source_xml(self) -> Mapping[str, str]:
        """Get the product source xml."""
        return await self._async_call_action(Service.PRODUCT, Product.SOURCE_XML)

    async def async_product_source_xml_change_count(self) -> Mapping[str, int]:
        """Get the product source xml change count."""
        return await self._async_call_action(Service.PRODUCT, Product.SOURCE_XML_CHANGE_COUNT)

    async def async_product_standby(self) -> Mapping[str, bool]:
        """Get the product standby status."""
        return await self._async_call_action(Service.PRODUCT, Product.STANDBY)

    # endregion
    # region Radio Service actions
    async def async_radio_channel(self) -> Mapping[str, str]:
        """Return the values of the Uri and Metadata state variables for the Radio source."""
        return await self._async_call_action(Service.RADIO, Radio.CHANNEL)

    async def async_radio_pause(self) -> None:
        """Pause any currently playing radio stream."""
        await self._async_call_action(Service.RADIO, Radio.PAUSE)

    async def async_radio_play(self) -> None:
        """Play the previously selected stream (set via either SetChannel or SetId)."""
        await self._async_call_action(Service.RADIO, Radio.PLAY)

    async def async_radio_set_channel(self, uri: str, metadata: str) -> None:
        """Set the uri and metadata for a new stream.

        uri: uri for channel
        metadata: metadata for radio channel
            must be valid metadata
        """
        await self._async_call_action(Service.RADIO, Radio.SET_CHANNEL, Uri=uri, Metadata=metadata)

    async def async_radio_stop(self) -> None:
        """Stop any currently playing radio stream."""
        await self._async_call_action(Service.RADIO, Radio.STOP)

    async def async_radio_transport_state(self) -> Mapping[str, str]:
        """Return the value of the TransportState state variable."""
        return await self._async_call_action(Service.RADIO, Radio.TRANSPORT_STATE)

    async def async_radio_id(self) -> Mapping[str, int]:
        """Return the value of the Id state variable."""
        return await self._async_call_action(Service.RADIO, Radio.ID)

    async def async_radio_set_id(self, value: int, uri: str) -> None:
        """Set the preset Id and uri for a new stream.

        :param value: the preset identifier
        :param uri: the uri of the stream
        """
        await self._async_call_action(Service.RADIO, Radio.SET_ID, Value=value, Uri=uri)

    async def async_radio_read(self, ident: int) -> Mapping[str, str]:
        """Given a channel preset Id, return its associated metadata.

        :param ident: the preset identifier
        """
        return await self._async_call_action(Service.RADIO, Radio.READ, Id=ident)

    async def async_radio_read_list(self, idlist: str) -> Mapping[str, str]:
        """Return associated metadata for a list of Ids.

        :param idlist: space separated list of Ids
        """
        return await self._async_call_action(Service.RADIO, Radio.READ_LIST, IdList=idlist)

    async def async_radio_id_array(self) -> Mapping[str, int | str]:
        """Return the value of the IdArray and Token state variables."""
        return await self._async_call_action(Service.RADIO, Radio.ID_ARRAY)

    async def async_radio_id_array_changed(self, token: int) -> Mapping[str, bool]:
        """Get the state variables for IdArrayChanged.

        :param token: value of token
        """
        return await self._async_call_action(Service.RADIO, Radio.ID_ARRAY_CHANGED, Token=token)

    async def async_radio_channels_max(self) -> Mapping[str, int]:
        """Return the value of the ChannelsMax state variable."""
        return await self._async_call_action(Service.RADIO, Radio.CHANNELS_MAX)

    async def async_radio_protocol_info(self) -> Mapping[str, str]:
        """Return the value of the ProtocolInfo state variable."""
        return await self._async_call_action(Service.RADIO, Radio.PROTOCOL_INFO)

    async def async_radio_refresh_presets(self) -> None:
        """Perform the action RefreshPresets."""
        await self._async_call_action(Service.RADIO, Radio.REFRESH_PRESETS)

    async def async_radio_seek_second_absolute(self, value: int) -> None:
        """Seek to an absolute second within the current stream, if permitted.

        :param value: second to seek
        """
        await self._async_call_action(Service.RADIO, Radio.SEEK_SECOND_ABSOLUTE, Value=value)

    async def async_radio_seek_second_relative(self, value: int) -> None:
        """Seek to a relative second within the current stream, if permitted.

        :param value: second to seek
        """
        await self._async_call_action(Service.RADIO, Radio.SEEK_SECOND_RELATIVE, Value=value)

    # endregion
    # region Receiver Service actions
    async def async_receiver_play(self) -> None:
        """Perform the action Play."""
        await self._async_call_action(Service.RECEIVER, Receiver.PLAY)

    async def async_receiver_stop(self) -> None:
        """Perform the action Stop."""
        await self._async_call_action(Service.RECEIVER, Receiver.STOP)

    async def async_receiver_set_sender(self, uri: str, metadata: str) -> None:
        """Set the uri and metadata of the sender to listen to.

        :param uri: uri of the sender
        :param metadata: metadata of the sender
        """
        await self._async_call_action(Service.RECEIVER, Receiver.SET_SENDER, Uri=uri, Metadata=metadata)

    async def async_receiver_sender(self) -> Mapping[str, str]:
        """Get the state variables for Sender."""
        return await self._async_call_action(Service.RECEIVER, Receiver.SENDER)

    async def async_receiver_protocol_info(self) -> Mapping[str, str]:
        """Get the state variables for ProtocolInfo."""
        return await self._async_call_action(Service.RECEIVER, Receiver.PROTOCOL_INFO)

    async def async_receiver_transport_state(self) -> Mapping[str, str]:
        """Get the state variables for TransportState."""
        return await self._async_call_action(Service.RECEIVER, Receiver.TRANSPORT_STATE)

    # endregion
    # region Sender Service actions
    async def async_sender_presentation_url(self) -> Mapping[str, str]:
        """Return the value of the PresentationUrl state variable."""
        return await self._async_call_action(Service.SENDER, Sender.PRESENTATION_URL)

    async def async_sender_metadata(self) -> Mapping[str, str]:
        """Return the value of the Metadata state variable."""
        return await self._async_call_action(Service.SENDER, Sender.METADATA)

    async def async_sender_audio(self) -> Mapping[str, bool]:
        """Return the value of the Audio state variable."""
        return await self._async_call_action(Service.SENDER, Sender.AUDIO)

    async def async_sender_status(self) -> Mapping[str, str]:
        """Return the value of the Status state variable."""
        return await self._async_call_action(Service.SENDER, Sender.STATUS)

    async def async_sender_status2(self) -> Mapping[str, str]:
        """Return the value of the Status state variable."""
        return await self._async_call_action(Service.SENDER, Sender.STATUS2)

    async def async_sender_enabled(self) -> Mapping[str, bool]:
        """Is the device capable of acting as a Songcast sender."""
        return await self._async_call_action(Service.SENDER, Sender.ENABLED)

    async def async_sender_attributes(self) -> Mapping[str, str]:
        """Return the value of the Attributes state variable."""
        return await self._async_call_action(Service.SENDER, Sender.ATTRIBUTES)

    # endregion
    # region Time Service actions
    async def async_time(self) -> Mapping[str, int]:
        """Report time information about progress through a track.

        :return: TrackCount, Duration, Seconds
        """
        return await self._async_call_action(Service.TIME, Time.TIME)

    # endregion
    # region Transport Service actions
    async def async_transport_pause(self) -> None:
        """Pause the current track or stream."""
        await self._async_call_action(Service.TRANSPORT, Transport.PAUSE)

    async def async_transport_play(self) -> None:
        """Play the current track or stream."""
        await self._async_call_action(Service.TRANSPORT, Transport.PLAY)

    async def async_transport_skip_next(self) -> None:
        """Move to the next track or stream."""
        await self._async_call_action(Service.TRANSPORT, Transport.SKIP_NEXT)

    async def async_transport_skip_previous(self) -> None:
        """Move to the previous track or stream."""
        await self._async_call_action(Service.TRANSPORT, Transport.SKIP_PREVIOUS)

    async def async_transport_state(self) -> Mapping[str, str]:
        """Return the current value of the TransportState state variable."""
        return await self._async_call_action(Service.TRANSPORT, Transport.TRANSPORT_STATE)

    async def async_transport_stop(self) -> None:
        """Stop the current track or stream."""
        await self._async_call_action(Service.TRANSPORT, Transport.STOP)

    async def async_transport_set_repeat(self, repeat: bool) -> None:
        """Set the Repeat state of the device.

        :param repeat: repeat the current playlist
        """
        await self._async_call_action(Service.TRANSPORT, Transport.SET_REPEAT, Repeat=repeat)

    async def async_transport_set_shuffle(self, shuffle: bool) -> None:
        """Set the Shuffle state of the device.

        :param shuffle: shuffle the current playlist
        """
        await self._async_call_action(Service.TRANSPORT, Transport.SET_SHUFFLE, Shuffle=shuffle)

    async def async_transport_seek_second_absolute(self, streamid: int, secondabsolute: int) -> None:
        """Seek to an absolute second within the current track or stream, if permitted."""
        await self._async_call_action(
            Service.TRANSPORT,
            Transport.SEEK_SECOND_ABSOLUTE,
            StreamId=streamid,
            SecondAbsolute=secondabsolute,
        )

    async def async_transport_seek_second_relative(self, streamid: int, secondrelative: int) -> None:
        """Seek to a second relative to the current track or stream position, if permitted."""
        await self._async_call_action(
            Service.TRANSPORT,
            Transport.SEEK_SECOND_RELATIVE,
            StreamId=streamid,
            SecondRelative=secondrelative,
        )

    async def async_transport_modes(self) -> Mapping[str, str]:
        """Return the value of the Modes state variable."""
        return await self._async_call_action(Service.TRANSPORT, Transport.MODES)

    async def async_transport_mode_info(self) -> Mapping[str, bool]:
        """Return the values of the ModeInfo state variables.

        :return: Mode, CanSkipNext, CanSkipPrev, CanRepeat, CanShuffle
        """
        return await self._async_call_action(Service.TRANSPORT, Transport.MODE_INFO)

    async def async_transport_stream_info(self) -> Mapping[str, int | bool]:
        """Return the values of the StreamInfo state variables.

        :return: StreamId, Seekable, Pausable
        """
        return await self._async_call_action(Service.TRANSPORT, Transport.STREAM_INFO)

    async def async_transport_stream_id(self) -> Mapping[str, int]:
        """Return the current value of the StreamId state variable.

        :return: StreamId
        """
        return await self._async_call_action(Service.TRANSPORT, Transport.STREAM_ID)

    async def async_transport_repeat(self) -> Mapping[str, bool]:
        """Return the current value of the Repeat state variable."""
        return await self._async_call_action(Service.TRANSPORT, Transport.REPEAT)

    async def async_transport_shuffle(self) -> Mapping[str, bool]:
        """Return the current value of the Shuffle state variable."""
        return await self._async_call_action(Service.TRANSPORT, Transport.SHUFFLE)

    async def async_transport_play_as(self, mode: str, command: str) -> None:
        """Start a new stream playing given a mode and command.

        :param mode: source or group of related sources
        :param command: mode specific command
        """
        await self._async_call_action(Service.TRANSPORT, Transport.PLAY_AS, Mode=mode, Command=command)

    # endregion
    # region Update Service actions
    async def async_update_apply(self) -> None:
        """Apply a software update."""
        await self._async_call_action(Service.UPDATE, Update.APPLY)

    async def async_update_apply2(self) -> None:
        """Apply a software update."""
        await self._async_call_action(Service.UPDATE, Update.APPLY2)

    async def async_update_check_now(self) -> Mapping[str, Any]:
        """Check the current status of the software."""
        return await self._async_call_action(Service.UPDATE, Update.CHECK_NOW)

    async def async_update_get_software_status(self) -> Mapping[str, str]:
        """Return the current status of the software."""
        return await self._async_call_action(Service.UPDATE, Update.GET_SOFTWARE_STATUS)

    # endregion
    # region Volume Service actions
    async def async_volume_set(self, volume_level: int) -> None:
        """Set the volume level.

        :param volume_level: the absolute value of the volume
        """
        await self._async_call_action(Service.VOLUME, Volume.SET_VOLUME, Value=volume_level)

    async def async_volume_set_mute(self, mute: bool) -> None:
        """Set the volume mute state.

        :param mute: the mute status of the volume to set
        """
        # if mute is False then the Volume will be unmuted
        # unmute only if explicitly boolean False
        if isinstance(mute, bool):
            await self._async_call_action(Service.VOLUME, Volume.SET_MUTE, Value=mute)
        else:
            raise TypeError("mute must be bool")

    async def async_volume_inc(self) -> None:
        """Increase the volume level by one."""
        await self._async_call_action(Service.VOLUME, Volume.VOLUME_INC)

    async def async_volume_dec(self) -> None:
        """Decrease the volume level by one."""
        await self._async_call_action(Service.VOLUME, Volume.VOLUME_DEC)

    # these actions return the values of state variables having been polled
    async def async_volume(self) -> Mapping[str, int]:
        """Return the value of the current volume level."""
        return await self._async_call_action(Service.VOLUME, Volume.VOLUME)

    async def async_volume_mute(self) -> Mapping[str, bool]:
        """Return the value of the current volume mute state."""
        return await self._async_call_action(Service.VOLUME, Volume.MUTE)

    async def async_volume_characteristics(self) -> Mapping[str, int]:
        """Return the value of the Characteristics state variables.

        :return: VolumeMax, VolumeUnity, VolumeSteps, VolumeMilliDbPerStep, BalanceMax, FadeMax
        """
        return await self._async_call_action(Service.VOLUME, Volume.CHARACTERISTICS)

    async def async_volume_set_no_unmute(self, value: int) -> None:
        """Set the absolute volume level without un-muting.

        :param value: the absolute volume level to set
        """
        await self._async_call_action(Service.VOLUME, Volume.SET_VOLUME_NO_UNMUTE, Value=value)

    async def async_volume_inc_no_unmute(self) -> None:
        """Increase the volume level by one without un-muting."""
        await self._async_call_action(Service.VOLUME, Volume.VOLUME_INC_NO_UNMUTE)

    async def async_volume_dec_no_unmute(self) -> None:
        """Decrease the volume level by one without un-muting."""
        await self._async_call_action(Service.VOLUME, Volume.VOLUME_DEC_NO_UNMUTE)

    async def async_volume_set_balance(self, value: int) -> None:
        """Set the volume left-right balance.

        :param value: the balance level to set
        """
        await self._async_call_action(Service.VOLUME, Volume.SET_BALANCE, Value=value)

    async def async_volume_balance_inc(self) -> None:
        """Increase the balance level by one."""
        await self._async_call_action(Service.VOLUME, Volume.BALANCE_INC)

    async def async_volume_balance_dec(self) -> None:
        """Decrease the balance level by one."""
        await self._async_call_action(Service.VOLUME, Volume.BALANCE_DEC)

    async def async_volume_balance(self) -> Mapping[str, int]:
        """Return the value of the Balance state variable."""
        return await self._async_call_action(Service.VOLUME, Volume.BALANCE)

    async def async_volume_set_fade(self, value: int) -> None:
        """Set the value of Fade (front-rear) balance.

        :param value: the Fade value to set
        """
        await self._async_call_action(Service.VOLUME, Volume.SET_FADE, Value=value)

    async def async_volume_fade_inc(self) -> None:
        """Increase the value of Fade (front-rear) balance by one."""
        await self._async_call_action(Service.VOLUME, Volume.FADE_INC)

    async def async_volume_fade_dec(self) -> None:
        """Decrease the value of Fade (front-rear) balance by one."""
        await self._async_call_action(Service.VOLUME, Volume.FADE_DEC)

    async def async_volume_fade(self) -> Mapping[str, int]:
        """Return the value of the Fade state variable."""
        return await self._async_call_action(Service.VOLUME, Volume.FADE)

    async def async_volume_limit(self) -> Mapping[str, int]:
        """Return value of the VolumeLimit state variable."""
        return await self._async_call_action(Service.VOLUME, Volume.VOLUME_LIMIT)

    async def async_volume_unity_gain(self) -> Mapping[str, bool]:
        """Return value of the UnityGain state variable."""
        return await self._async_call_action(Service.VOLUME, Volume.UNITY_GAIN)

    async def async_volume_offset(self, channel: str) -> Mapping[str, int]:
        """Return value of the VolumeOffset state variable.

        :param channel: the channel for which to return the volume offset

        :return: VolumeOffsetBinaryMilliDb
        """
        return await self._async_call_action(Service.VOLUME, Volume.VOLUME_OFFSET, Channel=channel)

    async def async_volume_set_offset(self, channel: str, volumeoffsetbinarymillidb: int) -> None:
        """Set the value of the VolumeOffset state variable.

        :param channel: the channel for which to set the volume offset
        :param volumeoffsetbinarymillidb: the volume offset in binary milli decibels (mibi dB)
        """
        await self._async_call_action(
            Service.VOLUME,
            Volume.SET_VOLUME_OFFSET,
            Channel=channel,
            VolumeOffsetBinaryMilliDb=volumeoffsetbinarymillidb,
        )

    async def async_volume_trim(self, channel: str) -> Mapping[str, int]:
        """Get the state variables for Trim.

        :param channel: the device channel to report on
        """
        return await self._async_call_action(Service.VOLUME, Volume.TRIM, Channel=channel)

    async def async_volume_set_trim(self, channel: str, trimbinarymillidb: int) -> None:
        """Trim the Volume of the channel.

        :param channel: the device channel
        :param trimbinarymillidb: the trim value in binary milli decibels (MiBi dB)
        """
        await self._async_call_action(
            Service.VOLUME,
            Volume.SET_TRIM,
            Channel=channel,
            TrimBinaryMilliDb=trimbinarymillidb,
        )

    # endregion

    # region Credentials Service State Variables
    @property
    def credentials_ids(self) -> str | None:
        """Space separated list of identifiers for services whose credentials can be set."""
        return self.get_state_variable_value(Service.CREDENTIALS, CredentialsState.IDS)

    @property
    def public_key(self) -> str | None:
        """RSA public key.

        Must be used to encrypt any/all passwords.
        """
        return self.get_state_variable_value(Service.CREDENTIALS, CredentialsState.PUBLIC_KEY)

    @property
    def sequence_number(self) -> int | None:
        """Sequence number.

        Increases whenever any aspect of state for any user of credentials listed in Ids changes.
        """
        return self.get_state_variable_value(Service.CREDENTIALS, CredentialsState.SEQUENCE_NUMBER)

    # endregion
    # region Info Service State Variables
    @property
    def info_track_count(self) -> int | None:
        """Return the value of the TrackCount state variable."""
        return self.get_state_variable_value(Service.INFO, InfoState.TRACK_COUNT)

    @property
    def info_details_count(self) -> int | None:
        """Return the value of the DetailsCount state variable."""
        return self.get_state_variable_value(Service.INFO, InfoState.DETAILS_COUNT)

    @property
    def info_metatext_count(self) -> int | None:
        """Return the value of the MetatextCount state variable."""
        return self.get_state_variable_value(Service.INFO, InfoState.METATEXT_COUNT)

    @property
    def info_uri(self) -> str | None:
        """Return the value of the Uri state variable."""
        return self.get_state_variable_value(Service.INFO, InfoState.URI)

    @property
    def info_metadata(self) -> str | None:
        """Return the value of the Metadata state variable."""
        return self.get_state_variable_value(Service.INFO, InfoState.METADATA)

    @property
    def info_duration(self) -> int | None:
        """Return the value of the Duration state variable."""
        return self.get_state_variable_value(Service.INFO, InfoState.DURATION)

    @property
    def info_bit_rate(self) -> int | None:
        """Return the value of the BitRate state variable."""
        return self.get_state_variable_value(Service.INFO, InfoState.BIT_RATE)

    @property
    def info_bit_depth(self) -> int | None:
        """Return the value of the BitDepth state variable."""
        return self.get_state_variable_value(Service.INFO, InfoState.BIT_DEPTH)

    @property
    def info_sample_rate(self) -> int | None:
        """Return the value of the SampleRate state variable."""
        return self.get_state_variable_value(Service.INFO, InfoState.SAMPLE_RATE)

    @property
    def info_lossless(self) -> bool | None:
        """Return the value of the Lossless state variable."""
        return self.get_state_variable_value(Service.INFO, InfoState.LOSSLESS)

    @property
    def info_codec_name(self) -> str | None:
        """Return the value of the CodecName state variable."""
        return self.get_state_variable_value(Service.INFO, InfoState.CODEC_NAME)

    @property
    def info_metatext(self) -> str | None:
        """Return the value of the Metatext state variable."""
        return self.get_state_variable_value(Service.INFO, InfoState.METATEXT)

    # endregion
    # region Pins Service State Variables
    @property
    def pins_device_max(self) -> int | None:
        """Return the value of the DeviceMax state variable."""
        return self.get_state_variable_value(Service.PINS, PinsState.DEVICE_MAX)

    @property
    def pins_account_max(self) -> int | None:
        """Return the value of the AccountMax state variable."""
        return self.get_state_variable_value(Service.PINS, PinsState.ACCOUNT_MAX)

    @property
    def pins_modes(self) -> str | None:
        """Return the value of the Modes state variable."""
        return self.get_state_variable_value(Service.PINS, PinsState.MODES)

    @property
    def pins_id_array(self) -> str | None:
        """Return the value of the IdArray state variable."""
        return self.get_state_variable_value(Service.PINS, PinsState.ID_ARRAY)

    @property
    def pins_cloud_connected(self) -> bool | None:
        """Return the value of the CloudConnected state variable."""
        return self.get_state_variable_value(Service.PINS, PinsState.CLOUD_CONNECTED)

    # endregion
    # region Playlist Service State Variables
    @property
    def playlist_transport_state(self) -> str | None:
        """Get playlist transport state."""
        return self.get_state_variable_value(Service.PLAYLIST, PlaylistState.TRANSPORT_STATE)

    @property
    def shuffle(self) -> bool | None:
        """Get playlist shuffle state."""
        return self.get_state_variable_value(Service.PLAYLIST, PlaylistState.SHUFFLE)

    @property
    def repeat(self) -> str | None:
        """Get playlist repeat state."""
        return self.get_state_variable_value(Service.PLAYLIST, PlaylistState.REPEAT)

    # endregion
    # region Product Service State Variables
    @property
    def product_room(self) -> str | None:
        """Return the room where product is located."""
        return self.get_state_variable_value(Service.PRODUCT, ProductState.PRODUCT_ROOM)

    @property
    def product_name(self) -> str | None:
        """Return the name of the product."""
        return self.get_state_variable_value(Service.PRODUCT, ProductState.PRODUCT_NAME)

    @property
    def product_manufacturer_name(self) -> str | None:
        """Return the value of the ManufacturerName state variable."""
        return self.get_state_variable_value(Service.PRODUCT, ProductState.MANUFACTURER_NAME)

    @property
    def product_manufacturer_info(self) -> str | None:
        """Return the value of the ManufacturerInfo state variable."""
        return self.get_state_variable_value(Service.PRODUCT, ProductState.MANUFACTURER_INFO)

    @property
    def product_manufacturer_url(self) -> str | None:
        """Return the value of the ManufacturerUrl state variable."""
        return self.get_state_variable_value(Service.PRODUCT, ProductState.MANUFACTURER_URL)

    @property
    def product_manufacturer_image_uri(self) -> str | None:
        """Return the value of the ManufacturerImageUri state variable."""
        return self.get_state_variable_value(Service.PRODUCT, ProductState.MANUFACTURER_IMAGE_URI)

    @property
    def product_model_name(self) -> str | None:
        """Return the value of the ModelName state variable."""
        return self.get_state_variable_value(Service.PRODUCT, ProductState.MODEL_NAME)

    @property
    def product_model_info(self) -> str | None:
        """Return the value of the ModelInfo state variable."""
        return self.get_state_variable_value(Service.PRODUCT, ProductState.MODEL_INFO)

    @property
    def product_model_url(self) -> str | None:
        """Return the value of the ModelUrl state variable."""
        return self.get_state_variable_value(Service.PRODUCT, ProductState.MODEL_URL)

    @property
    def product_model_image_uri(self) -> str | None:
        """Return the value of the ModelImageUri state variable."""
        return self.get_state_variable_value(Service.PRODUCT, ProductState.MODEL_IMAGE_URI)

    @property
    def product_info(self) -> str | None:
        """Return the value of the ProductInfo state variable."""
        return self.get_state_variable_value(Service.PRODUCT, ProductState.PRODUCT_INFO)

    @property
    def product_url(self) -> str | None:
        """Return the value of the ProductUrl state variable."""
        return self.get_state_variable_value(Service.PRODUCT, ProductState.PRODUCT_URL)

    @property
    def product_image_uri(self) -> str | None:
        """Return the value of the ProductImageUri state variable."""
        return self.get_state_variable_value(Service.PRODUCT, ProductState.PRODUCT_IMAGE_URI)

    @property
    def product_image_hires_uri(self) -> str | None:
        """Return the value of the ProductImageHiresUri state variable."""
        return self.get_state_variable_value(Service.PRODUCT, ProductState.PRODUCT_IMAGE_HIRES_URI)

    @property
    def product_standby(self) -> bool | None:
        """Return the value of the Standby state variable."""
        return self.get_state_variable_value(Service.PRODUCT, ProductState.STANDBY)

    @property
    def product_standby_transitioning(self) -> bool | None:
        """Return the value of the StandbyTransitioning state variable."""
        return self.get_state_variable_value(Service.PRODUCT, ProductState.STANDBY_TRANSITIONING)

    @property
    def product_source_index(self) -> int | None:
        """Return the value of the SourceIndex state variable."""
        return self.get_state_variable_value(Service.PRODUCT, ProductState.SOURCE_INDEX)

    @property
    def product_source_count(self) -> int | None:
        """Return the value of the SourceCount state variable."""
        return self.get_state_variable_value(Service.PRODUCT, ProductState.SOURCE_COUNT)

    @property
    def product_source_xml(self) -> str | None:
        """Return the value of the SourceXml state variable."""
        return self.get_state_variable_value(Service.PRODUCT, ProductState.SOURCE_XML)

    @property
    def product_attributes(self) -> str | None:
        """Return the value of the Attributes state variable."""
        return self.get_state_variable_value(Service.PRODUCT, ProductState.ATTRIBUTES)

    # endregion
    # region Radio Service State Variables
    @property
    def radio_uri(self) -> str | None:
        """Return the value of the Uri state variable."""
        return self.get_state_variable_value(Service.RADIO, RadioState.URI)

    @property
    def radio_metadata(self) -> str | None:
        """Return the value of the Metadata state variable."""
        return self.get_state_variable_value(Service.RADIO, RadioState.METADATA)

    @property
    def radio_transport_state(self) -> str | None:
        """Return the value of the TransportState state variable."""
        return self.get_state_variable_value(Service.RADIO, RadioState.TRANSPORT_STATE)

    @property
    def radio_id(self) -> int | None:
        """Return the value of the Id state variable."""
        return self.get_state_variable_value(Service.RADIO, RadioState.ID)

    @property
    def radio_id_array(self) -> str | None:
        """Return the value of the IdArray state variable."""
        return self.get_state_variable_value(Service.RADIO, RadioState.ID_ARRAY)

    @property
    def radio_channels_max(self) -> int | None:
        """Return the value of the ChannelsMax state variable."""
        return self.get_state_variable_value(Service.RADIO, RadioState.CHANNELS_MAX)

    @property
    def radio_protocol_info(self) -> str | None:
        """Return the value of the ProtocolInfo state variable."""
        return self.get_state_variable_value(Service.RADIO, RadioState.PROTOCOL_INFO)

    # endregion
    # region Receiver Service State Variables
    @property
    def receiver_metadata(self) -> str | None:
        """The metadata of the sender to listen to."""
        return self.get_state_variable_value(Service.RECEIVER, ReceiverState.METADATA)

    @property
    def receiver_uri(self) -> str | None:
        """The URI of the sender to listen to."""
        return self.get_state_variable_value(Service.RECEIVER, ReceiverState.URI)

    @property
    def receiver_protocol_info(self) -> str | None:
        """Reports the protocols supported."""
        return self.get_state_variable_value(Service.RECEIVER, ReceiverState.PROTOCOL_INFO)

    @property
    def receiver_transport_state(self) -> str | None:
        """Reports the receiver transport state."""
        return self.get_state_variable_value(Service.RECEIVER, ReceiverState.TRANSPORT_STATE)

    # endregion
    # region Sender Service State Variables
    @property
    def sender_audio(self) -> bool | None:
        """Is audio currently available from this Sender."""
        return self.get_state_variable_value(Service.SENDER, SenderState.AUDIO)

    @property
    def sender_metadata(self) -> str | None:
        """Provides basic information about the sender in DIDL-Lite format."""
        return self.get_state_variable_value(Service.SENDER, SenderState.METADATA)

    @property
    def sender_presentation_url(self) -> str | None:
        """Reports the url of a presentation page."""
        return self.get_state_variable_value(Service.SENDER, SenderState.PRESENTATION_URL)

    @property
    def sender_status2(self) -> str | None:
        """Reports the status of the sender."""
        return self.get_state_variable_value(Service.SENDER, SenderState.STATUS2)

    @property
    def sender_enabled(self) -> bool | None:
        """Reports if Songcast sending is enabled."""
        return self.get_state_variable_value(Service.SENDER, SenderState.ENABLED)

    # endregion
    # region Time Service State Variables
    @property
    def track_count(self) -> int | None:
        """The number of tracks that have been played."""
        return self.get_state_variable_value(Service.TIME, TimeState.TRACK_COUNT)

    @property
    def time_duration(self) -> int | None:
        """The total length of the current track in seconds."""
        return self.get_state_variable_value(Service.TIME, TimeState.DURATION)

    @property
    def seconds(self) -> int | None:
        """The total length of time in seconds for which the current track has been playing."""
        return self.get_state_variable_value(Service.TIME, TimeState.SECONDS)

    # endregion
    # region Transport Service State Variables
    @property
    def transport_modes(self) -> str | None:
        """Return the value of the Modes state variable."""
        return self.get_state_variable_value(Service.TRANSPORT, TransportState.MODES)

    @property
    def transport_can_skip_next(self) -> bool | None:
        """Return the value of the CanSkipNext state variable."""
        return self.get_state_variable_value(Service.TRANSPORT, TransportState.CAN_SKIP_NEXT)

    @property
    def transport_can_skip_previous(self) -> bool | None:
        """Return the value of the CanSkipPrevious state variable."""
        return self.get_state_variable_value(Service.TRANSPORT, TransportState.CAN_SKIP_PREVIOUS)

    @property
    def transport_can_repeat(self) -> bool | None:
        """Return the value of the CanRepeat state variable."""
        return self.get_state_variable_value(Service.TRANSPORT, TransportState.CAN_REPEAT)

    @property
    def transport_can_shuffle(self) -> bool | None:
        """Return the value of the CanShuffle state variable."""
        return self.get_state_variable_value(Service.TRANSPORT, TransportState.CAN_SHUFFLE)

    @property
    def transport_stream_id(self) -> int | None:
        """Return the value of the StreamId state variable."""
        return self.get_state_variable_value(Service.TRANSPORT, TransportState.STREAM_ID)

    @property
    def transport_can_seek(self) -> bool | None:
        """Return the value of the CanSeek state variable."""
        return self.get_state_variable_value(Service.TRANSPORT, TransportState.CAN_SEEK)

    @property
    def transport_can_pause(self) -> bool | None:
        """Return the value of the CanPause state variable."""
        return self.get_state_variable_value(Service.TRANSPORT, TransportState.CAN_PAUSE)

    @property
    def transport_state(self) -> str | None:
        """Return the value of the TransportState state variable for the active source.

        Return None if value cannot be determined
        """
        if self.has_transport_state:
            return self.get_state_variable_value(Service.TRANSPORT, TransportState.TRANSPORT_STATE)
        # transport service transport_state is not available
        active_source_type = None
        if self.product_source_xml is not None:
            try:
                source_xml = DET.fromstring(self.product_source_xml)
                active_index = self.product_source_index
                if active_index is not None:
                    active_source_type = source_xml[active_index].find("Type")
                    if active_source_type is not None:
                        active_source_type = active_source_type.text
            except DET.ParseError as error:
                _LOGGER.error("Value is not valid XML - %s", error.msg)

        match active_source_type:
            case ProductSourceType.PLAYLIST:
                return self.playlist_transport_state
            case ProductSourceType.RADIO:
                return self.radio_transport_state
            case ProductSourceType.RECEIVER:
                return self.receiver_transport_state
            case _:
                _LOGGER.warning("Unhandled source type: %s", active_source_type)
        return None

    @property
    def transport_repeat(self) -> bool | None:
        """Return the value of the Repeat state variable."""
        return self.get_state_variable_value(Service.TRANSPORT, TransportState.REPEAT)

    @property
    def transport_shuffle(self) -> bool | None:
        """Return the value of the Shuffle state variable."""
        return self.get_state_variable_value(Service.TRANSPORT, TransportState.SHUFFLE)

    # endregion
    # region Update Service State Variables
    @property
    def update_software_status(self) -> str | None:
        """Return the value of the SoftwareStatus state variable."""
        return self.get_state_variable_value(Service.UPDATE, UpdateState.SOFTWARE_STATUS)

    @property
    def update_executor_status(self) -> str | None:
        """Return the value of the ExecutorStatus state variable."""
        return self.get_state_variable_value(Service.UPDATE, UpdateState.EXECUTOR_STATUS)

    @property
    def update_job_status(self) -> str | None:
        """Return the value of the JobStatus state variable."""
        return self.get_state_variable_value(Service.UPDATE, UpdateState.JOB_STATUS)

    @property
    def update_recover_supported(self) -> bool | None:
        """Return the value of the RecoverSupported state variable."""
        return self.get_state_variable_value(Service.UPDATE, UpdateState.RECOVER_SUPPORTED)

    # endregion
    # region Volume Service State Variables
    @property
    def volume(self) -> int | None:
        """Return the Volume level."""
        volume_level = self.get_state_variable_value(Service.VOLUME, VolumeState.VOLUME)
        if not isinstance(volume_level, int):
            volume_level = None
        return volume_level

    @property
    def is_muted(self) -> bool | None:
        """Get mute status."""
        return self.get_state_variable_value(Service.VOLUME, VolumeState.MUTE)

    # endregion

    # region some has_* functions purely for convenience
    # use "self._action(<service>, <action>) is not None" for other combinations
    # alternatively check service and action independently
    # using <device>.has_service() and <service>.has_action()
    @property
    def has_product_set_source_index(self) -> bool:
        """Service Product has action SetSourceIndex."""
        return self._action(Service.PRODUCT, Product.SET_SOURCE_INDEX) is not None

    @property
    def has_product_set_standby(self) -> bool:
        """Service Product has action SetStandby."""
        return self._action(Service.PRODUCT, Product.SET_STANDBY) is not None

    @property
    def has_product_standby(self) -> bool:
        """Service Product has action Standby."""
        return self._action(Service.PRODUCT, Product.STANDBY) is not None

    @property
    def has_transport_play(self) -> bool:
        """Service Transport has action Play."""
        return self._action(Service.TRANSPORT, Transport.PLAY) is not None

    @property
    def has_transport_pause(self) -> bool:
        """Service Transport has action Pause."""
        return self._action(Service.TRANSPORT, Transport.PAUSE) is not None

    @property
    def has_transport_state(self) -> bool:
        """Service Transport has action TransportState."""
        return self._action(Service.TRANSPORT, Transport.TRANSPORT_STATE) is not None

    @property
    def has_transport_stop(self) -> bool:
        """Service Transport has action Stop."""
        return self._action(Service.TRANSPORT, Transport.STOP) is not None

    @property
    def has_transport_skip_next(self) -> bool:
        """Service Transport has action SkipNext."""
        return self._action(Service.TRANSPORT, Transport.SKIP_NEXT) is not None

    @property
    def has_transport_skip_previous(self) -> bool:
        """Service Transport has action SkipPrevious."""
        return self._action(Service.TRANSPORT, Transport.SKIP_PREVIOUS) is not None

    @property
    def has_transport_set_repeat(self) -> bool:
        """Service Transport has action SetRepeat."""
        return self._action(Service.TRANSPORT, Transport.SET_REPEAT) is not None

    @property
    def has_transport_set_shuffle(self) -> bool:
        """Service Transport has action SetShuffle."""
        return self._action(Service.TRANSPORT, Transport.SET_SHUFFLE) is not None

    @property
    def has_transport_seek_second_absolute(self) -> bool:
        """Service Transport has action SeekSecondAbsolute."""
        return self._action(Service.TRANSPORT, Transport.SEEK_SECOND_ABSOLUTE) is not None

    @property
    def has_transport_seek_second_relative(self) -> bool:
        """Service Transport has action SeekSecondRelative."""
        return self._action(Service.TRANSPORT, Transport.SEEK_SECOND_RELATIVE) is not None

    @property
    def has_volume(self) -> bool:
        """Service Volume has action Volume."""
        return self._action(Service.VOLUME, Volume.VOLUME) is not None

    @property
    def has_volume_set(self) -> bool:
        """Service Volume has action SetVolume."""
        return self._action(Service.VOLUME, Volume.SET_VOLUME) is not None

    @property
    def has_volume_set_mute(self) -> bool:
        """Service Volume has action SetMute."""
        return self._action(Service.VOLUME, Volume.SET_MUTE) is not None

    @property
    def has_volume_mute(self) -> bool:
        """Service Volume has action Mute."""
        return self._action(Service.VOLUME, Volume.MUTE) is not None

    # endregion

    # region syntactic helpers
    async def async_active_source_index(self) -> int | None:
        """Get the active source index."""
        index = await self.async_product_source_index()
        if index is not None:
            return int(index["Value"])
        return None

    async def async_active_source(self) -> Mapping[str, str | bool] | None:
        """Get all details of the active source."""

        index = await self.async_active_source_index()
        if index is not None:
            source = await self.async_product_source(index)
        else:
            source = None
        return source

    async def async_active_source_name(self) -> str | None:
        """Get the name of the active source."""

        source_name = None
        active_source = await self.async_active_source()
        if active_source is not None:
            source_name = str(active_source.get("Name"))
        return source_name

    async def async_active_source_type(self) -> str | None:
        """Get the type of the active source."""

        source_type = None
        active_source = await self.async_active_source()
        if active_source is not None:
            source_type = str(active_source.get("Type"))
        return source_type

    async def async_visible_sources(self) -> list[dict[str, str | int | None]]:
        """Get list of visible sources."""

        sources = []
        xml = await self.async_product_source_xml()
        if xml is not None:
            try:
                sources_list_xml = DET.fromstring(xml["Value"])

                for index, source_xml in enumerate(sources_list_xml):
                    visible = source_xml.findtext("Visible")
                    if visible in ("true", "1"):
                        sources.append(
                            {
                                "Index": index,
                                "Name": source_xml.findtext("Name"),
                                "Type": source_xml.findtext("Type"),
                                "SystemName": source_xml.findtext("SystemName"),
                            }
                        )
            except DET.ParseError as error:
                _LOGGER.error("Value is not valid XML - %s", error.msg)

        return sources

    async def async_play(self) -> None:
        """Play."""

        if self.has_transport_play:
            await self.async_transport_play()
        else:
            active_source_type = await self.async_active_source_type()
            match active_source_type:
                case ProductSourceType.RADIO:
                    await self.async_radio_play()
                case ProductSourceType.PLAYLIST:
                    await self.async_playlist_play()
                case ProductSourceType.RECEIVER:
                    await self.async_receiver_play()
                case _:
                    _LOGGER.warning("Unhandled source type: %s", active_source_type)

    async def async_stop(self) -> None:
        """Issue a Stop command.

        Stop using Transport service if available, otherwise Stop using active source.
        However, if transport state is currently stopped then do nothing.
        This is to avoid upnp error: 701 (Transition not available) from some devices e.g. BubbleUpnpServer
        """

        if self.has_transport_stop:
            # guard against raising error if transition would raise error
            if self.transport_state != TransportStateAllowedValues.STOPPED:
                await self.async_transport_stop()
        else:
            active_source_type = await self.async_active_source_type()
            match active_source_type:
                case ProductSourceType.RADIO:
                    await self.async_radio_stop()
                case ProductSourceType.PLAYLIST:
                    await self.async_playlist_stop()
                case ProductSourceType.RECEIVER:
                    await self.async_receiver_stop()
                case _:
                    _LOGGER.warning("Unhandled source type: %s", active_source_type)

    async def async_pause(self) -> None:
        """Pause."""

        if self.has_transport_pause:
            # guard against raising error if transition would raise error
            if self.transport_state not in (TransportStateAllowedValues.STOPPED, TransportStateAllowedValues.PAUSED):
                await self.async_transport_pause()
        else:
            active_source_type = await self.async_active_source_type()
            match active_source_type:
                case ProductSourceType.RADIO:
                    await self.async_radio_pause()
                case ProductSourceType.PLAYLIST:
                    await self.async_playlist_pause()
                case ProductSourceType.RECEIVER:
                    await self.async_receiver_stop()  # Receiver does not support pause so just stop
                case _:
                    _LOGGER.warning("Unhandled source type: %s", active_source_type)

    def has_source_type(self, product_source_type: ProductSourceType) -> bool | None:
        """Return True if profile has source type.

        None indicates not yet possible to determine source types
        Test for None before using boolean return value
        :param product_source_type: the product source type
        """
        if self.product_source_xml is not None:
            source_type: str = product_source_type.value  # py310
            try:
                parsed_xml = DET.fromstring(str(self.product_source_xml))
                return len(parsed_xml.findall(f'.//Source[Type="{source_type}"]')) > 0
            except DET.ParseError as error:
                _LOGGER.error("source_xml is not valid XML - %s", error.msg)
        else:
            _LOGGER.warning("source_xml is not populated")

        return None

    # endregion

    # region core methods
    async def _async_call_action(self, service_name: str, action_name: str, **kwargs: Any) -> Mapping[str, Any]:
        """Call service action by name with arguments.

        :param service_name: name of the service
        :param action_name: name of action to call

        raise error if service, action or combination is bad
        """

        action = self._action(service_name, action_name)
        if not action:  # isolate cause of failure and raise appropriate error
            service = self._service(service_name)
            if service is None:
                raise UpnpError(f"Bad service {service_name}")
            raise UpnpError(f"Bad action {action_name} for service {service_name}")

        result = await action.async_call(**kwargs)
        return result

    def get_state_variable_value(self, service_name: str, state_variable_name: str) -> Any | None:
        """Return value of state variable.

        :param service_name: name of the service
        :param state_variable_name: name of state variable

        :return: value of state variable or None if either service or state variable not found

        Note that the corresponding service-action should be polled first, or service subscribed,
        to assign a value to the variable
        """
        service = self._service(service_name)

        if service is None:
            _LOGGER.debug("Missing Service %s", service_name)
        else:
            state_var = self._state_variable(service_name, state_variable_name)
            if state_var is not None:
                return state_var.value
            _LOGGER.debug("Missing State Variable %s:%s", service_name, state_variable_name)
        return None

    async def async_update_state_variables(self, do_ping: bool = True) -> None:
        """Retrieve the latest values for all state variables of interesting services.

        :param do_ping: Poll device first to check if it is available (online).
        """
        if do_ping:
            await self.profile_device.async_ping()

        for service in self.device.all_services:
            if self._interesting_service(service):
                svc_identifier = service.service_id.split(":")[-1]
                actions_with_rsv = self.get_actions_with_state_variables(svc_identifier)
                await self._async_poll_state_variables(svc_identifier, actions_with_rsv)

    def get_actions_with_state_variables(self, service_name: str) -> Sequence[str]:
        """Create list of actions which have associated related state variables.

        :param service_name: the name of the service to process

        :return: list, possibly empty, of actions which have related state variables
        """
        actions = set()
        service = self._service(service_name)
        if not service:
            _LOGGER.debug("Can't find service %s", service_name)
        else:
            for action_name in service.actions:
                action = service.action(action_name)
                for arg in action.arguments:
                    if arg.direction == "out" and arg.related_state_variable.send_events:
                        actions.add(action_name)
                # actions that need input parameters will have to be managed by hand
                for arg in action.arguments:
                    if arg.direction == "in":
                        actions.discard(action_name)
        return list(actions)

    # endregion

    # region miscellaneous functions
    async def async_playlist_last_id(self) -> int:
        """Return the last id of the playlist."""

        decoded = []
        last_id: int = 0
        id_array = await self.async_playlist_id_array()
        if id_array is not None:
            id_array_value = id_array.get("Array")
            if id_array_value is not None:
                decoded = _decode_id_array(id_array_value)
            if len(decoded) > 0:
                last_id = decoded[-1]
        return last_id

    async def async_pins_set_device_metadata(self, pin_metadata: dict) -> None:
        """Set Pins service device using single metadata dictionary.

        :param pin_metadata: dictionary containing necessary metadata
        """
        keys = (
            "id",
            "mode",
            "type",
            "uri",
            "title",
            "description",
            "artworkUri",
            "shuffle",
        )
        if all(key in pin_metadata for key in keys):
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
        else:
            _LOGGER.warning("pin_metadata has invalid key(s): %s", pin_metadata)

    # endregion


# region functions independent of class
def id_list_to_string(list_int: list) -> str:
    """Convert ID list to space separated string.

    Invalid IDs (those that are 0 or negative) are discarded.
    """
    return " ".join(map(str, filter(lambda x: x > 0, list_int)))


def _decode_id_array(b64_id_array: str) -> list:
    """Convert base64 encoded list to list of integers."""

    array_int = []
    encoded_as_bytes = b64_id_array.encode("utf-8")
    try:
        decoded = base64.b64decode(encoded_as_bytes, validate=True)
    except binascii.Error as exception:
        raise ValueError("Invalid base64 encoding.") from exception

    if len(decoded) % 4 == 0:  # must be interpretable as 4 byte integers
        array_int = list(struct.unpack(">" + "I" * (len(decoded) // 4), decoded))
    else:
        _LOGGER.warning("Id array not parsable as 4-byte integers: %s", b64_id_array)

    return array_int


# endregion
