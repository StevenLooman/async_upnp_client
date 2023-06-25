async_upnp_client 0.34.0 (2023-06-25)
=====================================

Features
--------

- Support server event subscription (@PhracturedBlue) (#162)
- UpnpServer supports returning plain values from server Actions (@PhracturedBlue)

  Note that the values are still coerced by its related UpnpStateVariable. (#166)
- Server supports deferred SSDP responses via MX header (@PhracturedBlue) (#168)
- Support backwards compatible service/device types (@PhracturedBlue) (#169)
- Enable servers to define custom routes (@PhracturedBlue) (#170)
- Drop Python 3.7 support. (#171)


async_upnp_client 0.33.2 (2023-05-21)
=====================================

Features
--------

- Handle negative values for the bytes/traffic counters in IGDs.

  Some IGDs implement the counters as i4 (4 byte integer) instead of
  ui4 (unsigned 4 byte integer). This change tries to work around this by applying
  an offset of `2**31`. To access the original value, use the variables with a
  `_original` suffix. (#157)


Bugfixes
--------

- Now properly send ssdp:byebye when server is stopped. (#158)
- Fix indexing bug in cli parsing scope_id in IPv6 target (@senarvi) (#159)


Misc
----

- #160, #163, #164, #165


async_upnp_client 0.33.1 (2023-01-30)
=====================================

Bugfixes
--------

- Don't crash on empty LOCATION header in SSDP message. (#154)


async_upnp_client 0.33.0 (2022-12-20)
=====================================

Features
--------

- Provide sync callbacks too, next to async callbacks.

  By using sync callbacks, the number of tasks created is reduced. Async callbacks
  are still supported, though some parameters are renamed to explicitly note the
  callback is async.

  Also, the lock in `SsdpDeviceTracker` is removed and thus is no longer a
  `contextlib.AbstractAsyncContextManager`. (provide_sync_callbacks)


Bugfixes
--------

- Change comma splitting code in the DLNA module to better handle misbehaving clients. (safer-comma-splitting)


async_upnp_client 0.32.3 (2022-12-02)
=====================================

Bugfixes
--------

- Add support for i8 and ui8 types of UPnP descriptor variables. This fixes
  parsing of Gerbera's `A_ARG_TYPE_PosSecond` state variable. (@chishm) (int8)


Misc
----

- dev_deps: Stricter pinning of development dependencies.


async_upnp_client 0.32.2 (2022-11-05)
=====================================

Bugfixes
--------

- Hostname was always expected to be a valid value when determining IP version. (hostname_unset_fix)
- Require scope_id to be set for source and target when creating a ssdp socket. (ipv6_scope_id_unset)


Misc
----

- #150


async_upnp_client 0.32.1 (2022-10-23)
=====================================

Bugfixes
--------

- Be more tolerant about extracting UDN from USN. Before, it was expecting the literal `uuid:`. Now it is case insensitive. (more_tolerant_udn_from_usn_parsing)
- Several SSDP related fixes for UPnPServer. (ssdp_fixes)
- Fix a race condition in `server.SsdpAdvertisementAnnouncer` regarding protocol initialization. (#148)
- Fixes with regard to binding socket(s) for SSDP on macOS. Includes changes/improvements for Linux and Windows as well. (#149)


async_upnp_client 0.32.0 (2022-10-10)
=====================================

Features
--------

- Add ability to build a upnp server.

  This creates a complete upnp server, including a SSDP search responder and regular SSDP advertisement broadcasting. See the scripts ``contrib/dummy_router.py`` or ``contrib/dummy_tv.py`` for examples. (#143)
- Add options to UpnpServer + option to always respond with root device.

  The option is to ensure that Windows (11) always sees the device in the Network view in the Explorer. (#145)
- Provide a single method to retrieve commonly updated data. This contains:
  * traffic counters:
     * bytes_received
     * bytes_sent
     * packets_received
     * packets_sent
  * status_info:
     * connection_status
     * last_connection_error
     * uptime
  * external_ip_address
  * derived traffic counters:
     * kibibytes_per_sec_received (since last call)
     * kibibytes_per_sec_sent (since last call)
     * packets_per_sec_received (since last call)
     * packets_per_sec_sent (since last call)

  Also let IgdDevice calculate derived traffic counters (value per second). (#146)


Bugfixes
--------

- * `DmrDevice.async_wait_for_can_play` will poll for changes to the `CurrentTransportActions` state variable, instead of just waiting for events.
  * `DmrDevice._fetch_headers` will perform a GET with a Range for the first byte, to minimise unnecessary network traffic. (@chishm) (#142)
- Breaking change: ``ST`` stands for search target, not service type. (#144)


Misc
----

- dev_deps


async_upnp_client 0.31.2 (2022-06-19)
=====================================

Bugfixes
--------

- Cache decoding ssdp packets (@bdraco) (#141)


async_upnp_client 0.31.1 (2022-06-06)
=====================================

Bugfixes
--------

- Ignore the ``HOST``-header in ``SsdpListener``. When a device advertises on both IPv4 and IPV6, the advertisements
  have the header ``239.255.255.250:1900`` and ``[FF02::C]:1900``, respectively. Given that the ``SsdpListener`` did
  not ignore this header up to now, it was seen as a change and causing a reinitialisation in the Home Assistant
  ``upnp`` component. (#140)


async_upnp_client 0.31.0 (2022-05-28)
=====================================

Bugfixes
--------

- Fix errors raised when `AiohttpSessionRequester` is disconnected while writing a request body.

  The server is allowed to disconnect at any time during a request session, which point we want to retry the request.

  A disconnection could manifest as an `aiohttp.ServerDisconnectedError` if it happened between requests, or it could be `aiohttp.ClientOSError` if it happened while we are writing the request body. Both errors derive from `aiohttp.ClientConnectionError` for socket errors.

  Also use `repr` when encapsulating errors for easier debugging. (#139)


async_upnp_client 0.30.1 (2022-05-22)
=====================================

Bugfixes
--------

- Work around aiohttp sending invalid Host-header. When the device url contains
  a IPv6-addresshost with scope_id, aiohttp sends the scope_id with the
  Host-header. This causes problems with some devices, returning a HTTP 404
  error or perhaps a HTTP 400 error. (#138)


async_upnp_client 0.30.0 (2022-05-20)
=====================================

Features
--------

- Gracefully handle bad Get* state variable actions

  Some devices don't support all the Get* actions (e.g.
  GetTransportSettings) that return state variables. This could cause
  exceptions when trying to poll variables during an (initial) update. Now
  when an expected (state variable polling) action is missing, or gives a
  response error, it is logged but no exception is raised. (@chishm) (#137)


Misc
----

- #136


async_upnp_client 0.29.0 (2022-04-24)
=====================================

Features
--------

- Always use CaseInsensitiveDict for headers (@bdraco)

  Headers were typed to not always be a CaseInsensitiveDict but
  in practice they always were. By ensuring they are always a
  CaseInsensitiveDict we can reduce the number of string
  transforms since we already know when strings have been
  lowercased. (#135)


async_upnp_client 0.28.0 (2022-04-24)
=====================================

Features
--------

- Optimize location_changed (@bdraco) (#132)
- Optimize CaseInsensitiveDict usage (@bdraco) (#133)
- Include scope ID in link-local IPv6 host addresses (@chishm)

  When determining the local IPv6 address used to connect to a remote host,
  include the scope ID in the returned address string if using a link-local
  IPv6 address.

  This is needed to bind event listeners to the correct network interface. (#134)


async_upnp_client 0.27.0 (2022-03-17)
=====================================

Features
--------

- Breaking change: Don't include parts of the library from the ``async_upnp_client`` module. (#126)
- Don't raise parse errors if GET request returns an empty file.

  Added an exception to client_factory.py to handle an empty XML document.
  If XML document is invalid, scpd_el variable is replaced with a clean ElementTree. (#128)


Bugfixes
--------

- Don't set Content-Length header but let aiohttp calculate it. This prevents an invalid Content-Length header value when using characters which are encoded to more than one byte. (#129)


Misc
----

- bump2version, consolidate_setupcfg, towncrier


Pre-towncrier changes
=====================

0.26.0 (2022-03-06)

- DLNA DMR profile will pass ``media_url`` unmodified to SetAVTransportURI and SetNextAVTransportURI (@chishm)
- Poll DLNA DMR state variables when first connecting (@chishm)
- Add CurrentTransportActions to list of state variables to poll when DLNA DMR device is not successfully subscribed (@chishm)
- More forgiving parsing of ``Cache-Control`` header value
- ``UpnpProfileDevice`` can be used without an ``UpnpEventHandler``
- Store version in ``async_upnp_client.__version__``


0.25.0 (2022-02-22)

- Better handle multi-stack devices by de-duplicating search responses/advertisements from different IP versions in ``SsdpListener``
   - Use the parameter ``device_tracker`` to share the ``SsdpDeviceTracker`` between ``SsdpListener``s monitoring the same network
   - Note that the ``SsdpDeviceTracker`` is now locked by the ``SsdpListener`` in case it is shared.


0.24.0 (2022-02-12)

- Add new dummy_tv/dummy_router servers (@StevenLooman)
- Drop python 3.6 support, add python 3.10 support (@StevenLooman)
- Breaking change: Improve SSDP IPv6 support, for Python versions <3.9, due to missing IPv6Address.scope_id (@StevenLooman)
   - ``SsdpListener``, ``SsdpAdvertisementListener``, ``SsdpSearchListener``, ``UpnpProfileDevice`` now take ``AddressTupleVXType`` for source and target, instead of IPs
- Breaking change: Separate multi-listener event handler functionality from ``UpnpEventHandler`` into ``UpnpEventHandlerRegister`` (@StevenLooman)


0.23.5 (2022-02-06)

- Add new dummy_tv/dummy_router servers (@StevenLooman)
- Drop python 3.6 support, add python 3.10 support
- Ignore devices using link local addresses in their location (@Tigger2014, #119)


0.23.4 (2022-01-16)

- Raise ``UpnpXmlContentError`` when device has bad description XML (@chishm, #118)
- Raise ``UpnpResponseError`` for HTTP errors in UpnpFactory (@chishm, #118)
- Fix ``UpnpXmlParseError`` (@chishm, #118)


0.23.3 (2022-01-03)

- ``SsdpListener``: Fix error where a device seen through a search, then byebye-advertisement (@StevenLooman, #117)


0.23.2 (2021-12-22)

- Speed up combined_headers in ssdp_listener (@bdraco, #115)
- Add handling of broken SSDP-headers (#116)


0.23.1 (2021-12-18)

- Bump ``python-didl-lite`` to 1.3.2
- Log missing state vars instead of raising UpnpError in DmrDevice (@chishm)


0.23.0 (2021-11-28)

- Allow for renderers that do not provide a list of actions. (@Flameeyes)
- Fix parsing of allowedValueList (@StevenLooman)
- Add DMS profile for interfacing with DLNA Digital Media Servers (@chishm)
- More details reported in Action exceptions (@chishm)
- Fix type hints in ``description_cache`` (@epenet, @StevenLooman)


0.22.12 (2021-11-06)

- Relax async-timeout dependency, cleanup deprecated sync use (@frenck)


0.22.11 (2021-10-31)

- Poll state variables when event subscriptions are rejected (@chishm)


0.22.10 (2021-10-25)

- Fix byebye advertisements not propagated because missing location (@chishm)
- Require specific services for profile devices (@chishm)
- Bump ``python-didl-lite`` to 1.3.1


0.22.9 (2021-10-21)

- CLI: Don't crash on upnperrors on upnp-client subscribe (@rytilahti)
- DLNA/DMR Profile add support for (@chishm):
   - play mode (repeat and shuffle)
   - setting of play_media metadata
   - SetNextAVTransportURI
   - setting arbitrary metadata for SetAVTransportURI
   - playlist title
- Ignore Cache-Control headers when comparing for change (@bdraco)
- Fix Windows error: ``[WinError 10022] An invalid argument was supplied``
- Fix Windows error: ``[WinError 10049] The requested address is not valid in its context``


0.22.8 (2021-10-08)

- Log when async_http_request retries due to ServerDisconnectedError (@chishm)
- More robustness when extracting UDN from USN in ``ssdp.udn_from_headers``


0.22.7 (2021-10-08)

- Ignore devices with an invalid location in ``ssdp_listener.SsdpListener``
- More robustness in IGD profile when parsing StatusInfo
- Log warning instead of an error with subscription related problems in profile devices
- Ignore devices with a location pointing to localhost in ``ssdp_listener.SsdpListener``


0.22.6 (2021-10-08)

- Bump python-didl-lite to 1.3.0
- More robustness in ``ssdp_listener.SsdpListener`` by requiring a parsed UDN (from USN) and location


0.22.5 (2021-10-03)

- More robustness in IGD profile by not relying on keys always being there


0.22.4 (2021-09-28)

- DLNA/DMR Profile: Add media metadata properties (@chishm)


0.22.3 (2021-09-27)

- Fix race condition where the description is fetched many times (@bdraco)
- Retry on ServerDisconnectedError (@bdraco)


0.22.2 (2021-09-27)

- Fix DmrDevice._supports method always returning False (@chishm)
- More informative exception messages (@chishm)
- UpnpProfileDevice unsubscribes from services in parallel (@chishm)


0.22.1 (2021-09-26)

- Fix IGD profile
- Fix getting all services of root and embedded devices in upnp-client


0.22.0 (2021-09-25)

- Always propagate search responses from SsdpListener (@bdraco)
- Embedded device support, also fixes the problem where services from embedded devices ended up at the root device


0.21.3 (2021-09-14)

- Fix ``ssdp_listener.SsdpDeviceTracker`` to update device's headers upon ssdp:byebye advertisement (@chishm)
- Several optimizations related to ``ssdp_listener.SsdpListener`` (@bdraco)


0.21.2 (2021-09-12)

- Tweak CaseInsensitiveDict to continue to preserve case (@bdraco)


0.21.1 (2021-09-11)

- Log traffic before decoding response text from device
- Optimize header comparison (@bdraco)


0.21.0 (2021-09-05)

- More pylint/mypy
- Fixed NoneType exception in DmrDevice.media_image_url (@mkliche)
- Breaking change: Rename ``advertisement.UpnpAdvertisementListener`` to ``advertisement.SsdpAdvertisementListener``
- Breaking change: Rename ``search.SSDPListener`` to ``search.SsdpSearchListener``
- Add ``ssdp_listener.SsdpListener``, class to keep track of devices seen via SSDP advertisements and searches
- Breaking change: ``UpnpDevice.boot_id`` and ``UpnpDevice.config_id`` have been moved to ``UpnpDevice.ssdp_headers``, using the respecitive keys from the SSDP headers


0.20.0 (2021-08-17)

- Wrap XML ``ParseError`` in an error type derived from it and ``UpnpError`` too (@chishm)
- Breaking change: Calling ``async_start`` on ``SSDPListener`` no longer calls ``async_search`` immediately. (#77) @bdraco
- Breaking change: The ``target_ip`` argument of ``search.SSDPListener`` has been dropped and replaced with ``target`` which takes a ``AddressTupleVXType`` (#77) @bdraco
- Breaking change: The ``target_ip`` argument of ``search.async_search`` has been dropped and replaced with ``target`` which takes a ``AddressTupleVXType`` (#77) @bdraco


0.19.2 (2021-08-04)

- Clean up ``UpnpRequester``: Remove ``body_type`` parameter
- Allow for overriding the ``target`` in ``ssdp.SSDPListener.async_search()``
- Set SO_BROADCAST flag, fixes ``Permission denied`` error when sending to global broadcast address


0.19.1 (2021-07-21)

- Work around duplicate headers in SSDP responses (#74)


0.19.0 (2021-06-19)

- Rename ``profiles.dlna.DlanOrgFlags`` to ``DlnaOrgFlags`` to fix a typo (@chishm)
- Defer event callback URL determination until event subscriptions are created (@chishm)
- Add ``UpnpDevice.icons`` and ``UpnpProfileDevice.icon`` to get URLs to device icons (@chishm)
- Add more non-strict parsing of action responses (#68)
- Stick with ``asyncio.get_event_loop()`` for Python 3.6 compatibility
- asyncio and aiohttp exceptions are wrapped in exceptions derived from ``UpnpError`` to hide implementation details and make catching easier (@chishm)
- ``UpnpProfileDevice`` can resubscribe to services automatically, using an asyncio task (@chishm)


0.18.0 (2021-05-23)

- Add SSDPListener which is now the underlying code path for async_search and can be used as a long running listener (@bdraco)


0.17.0 (2021-05-09)

- Add UpnpFactory non_strict option, replacing disable_state_variable_validation and disable_unknown_out_argument_error
- UpnpAction tries non-versioned service type (#68) in non-strict mode
- Strip spaces, line endings and null characters before parsing XML (@apal0934)
- Properly parse and return subscription timeout
- More strip spaces, line engines and null characters before parsing XML


0.16.2 (2021-04-25)

- Improve performance of parsing headers by switching to aiohttp.http_parser.HeadersParser (@bdraco)


0.16.1 (2021-04-22)

- Don't double-unescape action responses (#50)
- Add ``UpnpDevice.service_id()`` to get service by service_id. (@bazwilliams)
- Fix 'was never awaited'-warning


0.16.0 (2021-03-30)

- Fix timespan formatting for content > 1h
- Try to fix invalid device encodings
- Rename ``async_upnp_client.traffic`` logger to ``async_upnp_client.traffic.upnp`` and add ``async_upnp_client.traffic.ssdp`` logger
- Added ``DeviceUpdater`` to support updating the ``UpnpDevice`` inline on changes to ``BOOTID.UPNP.ORG``/``CONFIGID.UPNP.ORG``/``LOCATION``
- Added support for PAUSED_PLAYBACK state (#56, @brgerig)
- Add ``DmrDevice.transport_state``, deprecate ``DmrDevice.state``
- Ignore prefix/namespace in DLNA-Events for better compatibility
- DLNA set_transport_uri: Allow supplying own meta_data (e.g. received from a content directory)
- DLNA set_transport_uri: Backwards incompatible change: Only media_uri and media_title are required.
                          To override mime_type, upnp_class or dlna_features create meta_data via construct_play_media_metadata()


0.15.0 (2021-03-13)

- Added ability to set additional HTTP headers (#51)
- Nicer error message on invalid Action Argument
- Store raw received argument value (#50)
- Be less strict about didl-lite
- Allow targeted announces (#53, @elupus)
- Support ipv6 search and advertisements (#54, @elupus)


0.14.15 (2020-11-01)

- Do not crash on empty XML file (@ekandler)
- Option to print timestamp in ISO8601 (@kitlaan)
- Option to not print LastChange subscription variable (@kitlaan)
- Test with Python 3.8 (@scop)
- Less stricter version pinning of ``python-didl-lite`` (@fabaff)
- Drop Python 3.5 support, upgrade ``pytest``/``pytest-asyncio``
- Convert type comments to annotations


0.14.14 (2020-04-25)

- Add support for fetching the serialNumber (@bdraco)


0.14.13 (2020-04-08)

- Expose ``device_type`` on ``UpnpDevice`` and ``UpnpProfileDevice``


0.14.12 (2019-11-12)

- Improve parsing of state variable types: date, dateTime, dateTime.tz, time, time.tz


0.14.11 (2019-09-08)

- Support state variable types: date, dateTime, dateTime.tz, time, time.tz


0.14.10 (2019-06-21)

- Ability to pass timeout argument to async_search


0.14.9 (2019-05-11)

- Fix service resubscription failure: wrong timeout format (@romaincolombo)
- Disable transport action checks for non capable devices (@romaincolombo)


0.14.8 (2019-05-04)

- Added the disable_unknown_out_argument_error to disable exception raising for not found arguments (@p3g4asus)


0.14.7 (2019-03-29)

- Better handle empty default values for state variables (@LooSik)


0.14.6 (2019-03-20)

- Fixes to CLI
- Handle invalid event-XML containing invalid trailing characters
- Improve constructing metadata when playing media on DLNA/DMR devices
- Upgrade to python-didl-lite==1.2.4 for namespacing changes


0.14.5 (2019-03-02)

- Allow overriding of callback_url in AiohttpNotifyServer (@KarlVogel)
- Check action/state_variable exists when retrieving it, preventing an error


0.14.4 (2019-02-04)

- Ignore unknown state variable changes via LastChange events


0.14.3 (2019-01-27)

- Upgrade to python-didl-lite==1.2.2 for typing info, add ``py.typed`` marker
- Add fix for HEOS-1 speakers: default subscription time-out to 9 minutes, only use channel Master (@stp6778)
- Upgrade to python-didl-lite==1.2.3 for bugfix


0.14.2 (2019-01-19)

- Fix parsing response of Action call without any return values


0.14.1 (2019-01-16)

- Fix missing async_upnp_client.profiles in package


0.14.0 (2019-01-14)

- Add __repr__ for UpnpAction.Argument and UPnpService.Action (@rytilahti)
- Support advertisements and rename discovery to search
- Use defusedxml to parse XML (@scop)
- Fix UpnpProfileDevice.async_search() + add UpnpProfileDevice.upnp_discover() for backwards compatibility
- Add work-around for win32-platform when using ``upnp-client search``
- Minor changes
- Typing fixes + automated type checking
- Support binding to IP(v4) for search and advertisements


0.13.8 (2018-12-29)

- Send content-type/charset on call-action, increasing compatibility (@tsvi)


0.13.7 (2018-12-15)

- Make UpnpProfileDevice.device public and add utility methods for device information


0.13.6 (2018-12-10)

- Add manufacturer, model_description, model_name, model_number properties to UpnpDevice


0.13.5 (2018-12-09)

- Minor refactorings: less private variables which are actually public (through properties) anyway
- Store XML-node at UpnpDevice/UpnpService/UpnpAction/UpnpAction.Argument/UpnpStateVariable
- Use http.HTTPStatus
- Try to be closer to the UPnP spec with regard to eventing


0.13.4 (2018-12-07)

- Show a bit more information on unexpected status from HTTP GET
- Try to handle invalid XML from LastChange event
- Pylint fixes


0.13.3 (2018-11-18)

- Add option to ``upnp-client`` to set timeout for device communication/discovery
- Add option to be strict (default false) with regard to invalid data
- Add more error handling to ``upnp-client``
- Add async_discovery
- Fix discovery-traffic not being logged to async_upnp_client.traffic-logger
- Add discover devices specific from/for Profile


0.13.2 (2018-11-11)

- Better parsing + robustness for media_duration/media_position in dlna-profile
- Ensure absolute URL in case a relative URL is returned for DmrDevice.media_image_url (with fix by @rytilahti)
- Fix events not being handled when subscribing to all services ('*')
- Gracefully handle invalid values from events by setting None/UpnpStateVariable.UPNP_VALUE_ERROR/None as value/value_unchecked
- Work-around for devices which don't send the SID upon re-subscribing


0.13.1 (2018-11-03)

- Try to subscribe if re-subscribe didn't work + push subscribe-related methods upwards to UpnpProfileDevice
- Do store min/max/allowed values at stateVariable even when disable_state_variable_validation has been enabled
- Add relative and absolute Seek commands to DLNA DMR profile
- Try harder to get a artwork picture for DLNA DMR Profile


0.13.0 (2018-10-27)

- Add support for discovery via SSDP
- Make IGD aware that certain actions live on WANPPP or WANIPC service


0.12.7 (2018-10-18)

- Log cases where a stateVariable has no sendEvents/sendEventsAttribute set at debug level, instead of warning


0.12.6 (2018-10-17)

- Handle cases where a stateVariable has no sendEvents/sendEventsAttribute set


0.12.5 (2018-10-13)

- Prevent error when not subscribed
- upnp-client is more friendly towards user/missing arguments
- Debug log spelling fix (@scop)
- Add some more IGD methods (@scop)
- Add some more IGD WANIPConnection methods (@scop)
- Remove new_ prefix from NatRsipStatusInfo fields, fix rsip_available type (@scop)
- Add DLNA RC picture controls + refactoring (@scop)
- Typing improvements (@scop)
- Ignore whitespace around state variable names in XML (@scop)
- Add basic printer support (@scop)


0.12.4 (2018-08-17)

- Upgrade python-didl-lite to 1.1.0


0.12.3 (2018-08-16)

- Install the command line tool via setuptools' console_scripts entrypoint (@mineo)
- Show available services/actions when unknown service/action is called
- Add configurable timeout to aiohttp requesters
- Add IGD device + refactoring common code to async_upnp_client.profile
- Minor fixes to CLI, logging, and state_var namespaces


0.12.2 (2018-08-05)

- Add TravisCI build
- Add AiohttpNotifyServer
- More robustness in DmrDevice.media_*
- Report service with device UDN


0.12.1 (2018-07-22)

- Fix examples/get_volume.py
- Fix README.rst
- Add aiohttp utility classes


0.12.0 (2018-07-15)

- Add upnp-client, move async_upnp_client.async_upnp_client to async_upnp_client.__init__
- Hide voluptuous errors, raise UpnpValueError
- Move UPnP eventing to UpnpEventHandler
- Do traffic logging in UpnpRequester
- Add DLNA DMR implementation/abstraction


0.11.2 (2018-07-05)

- Fix log message
- Fix typo in case of failed subscription (@yottatsa)


0.11.1 (2018-07-05)

- Log getting initial description XMLs with traffic logger as well
- Improve SUBSCRIBE and implement SUBSCRIBE-renew
- Add more type hints


0.11.0 (2018-07-03)

- Add more type hints
- Allow ignoring of data validation for state variables, instead of just min/max values


0.10.1 (2018-06-30)

- Fixes to setup.py and setup.cfg
- Do not crash on empty body on notifications (@rytilahti)
- Styling/linting fixes
- modelDescription from device description XML is now optional
- Move to async/await syntax, from old @asyncio.coroutine/yield from syntax
- Allow ignoring of allowedValueRange for state variables
- Fix handling of UPnP events and add utils to handle DLNA LastChange events
- Do not crash when state variable is not available, allow easier event debugging (@rytilahti)


0.10.0 (2018-05-27)

- Remove aiohttp dependency, user is now free/must now provide own UpnpRequester
- Don't depend on pytz
- Proper (un)escaping of received and sent data in UpnpActions
- Add async_upnp_client.traffic logger for easier monitoring of traffic
- Support more data types


0.9.1 (2018-04-28)

- Support old style ``sendEvents``
- Add response-body when an error is received when calling an action
- Fixes to README
- Fixes to setup


0.9.0 (2018-03-18)

- Initial release
