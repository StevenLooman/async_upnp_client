Changes
=======

0.22.2 (unreleased)


0.22.1 (2021-09-26)

- Fix IGD profile
- Fix getting all services of root and embedded devices in upnp-client


0.22.0 (2021-09-25)

- Always propagate search responses from SsdpListener (@bdraco)
- Embedded device support, also fixes the problem where services from embedded devices ended up at the root device


0.21.3 (2021-09-14)

- Fix `ssdp_listener.SsdpDeviceTracker` to update device's headers upon ssdp:byebye advertisement (@chishm)
- Several optimizations related to `ssdp_listener.SsdpListener` (@bdraco)


0.21.2 (2021-09-12)

- Tweak CaseInsensitiveDict to continue to preserve case (@bdraco)


0.21.1 (2021-09-11)

- Log traffic before decoding response text from device
- Optimize header comparison (@bdraco)


0.21.0 (2021-09-05)

- More pylint/mypy
- Fixed NoneType exception in DmrDevice.media_image_url (@mkliche)
- Breaking change: Rename `advertisement.UpnpAdvertisementListener` to `advertisement.SsdpAdvertisementListener`
- Breaking change: Rename `search.SSDPListener` to `search.SsdpSearchListener`
- Add `ssdp_listener.SsdpListener`, class to keep track of devices seen via SSDP advertisements and searches
- Breaking change: `UpnpDevice.boot_id` and `UpnpDevice.config_id` have been moved to `UpnpDevice.ssdp_headers`, using the respecitive keys from the SSDP headers


0.20.0 (2021-08-17)

- Wrap XML `ParseError` in an error type derived from it and `UpnpError` too (@chishm)
- Breaking change: Calling `async_start` on `SSDPListener` no longer calls `async_search` immediately. (#77) @bdraco
- Breaking change: The `target_ip` argument of `search.SSDPListener` has been dropped and replaced with `target` which takes a `AddressTupleVXType` (#77) @bdraco
- Breaking change: The `target_ip` argument of `search.async_search` has been dropped and replaced with `target` which takes a `AddressTupleVXType` (#77) @bdraco


0.19.2 (2021-08-04)

- Clean up `UpnpRequester`: Remove `body_type` parameter
- Allow for overriding the `target` in `ssdp.SSDPListener.async_search()`
- Set SO_BROADCAST flag, fixes `Permission denied` error when sending to global broadcast address


0.19.1 (2021-07-21)

- Work around duplicate headers in SSDP responses (#74)


0.19.0 (2021-06-19)

- Rename `profiles.dlna.DlanOrgFlags` to `DlnaOrgFlags` to fix a typo (@chishm)
- Defer event callback URL determination until event subscriptions are created (@chishm)
- Add `UpnpDevice.icons` and `UpnpProfileDevice.icon` to get URLs to device icons (@chishm)
- Add more non-strict parsing of action responses (#68)
- Stick with `asyncio.get_event_loop()` for Python 3.6 compatibility
- asyncio and aiohttp exceptions are wrapped in exceptions derived from `UpnpError` to hide implementation details and make catching easier (@chishm)
- `UpnpProfileDevice` can resubscribe to services automatically, using an asyncio task (@chishm)


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
- Add `UpnpDevice.service_id()` to get service by service_id. (@bazwilliams)
- Fix 'was never awaited'-warning


0.16.0 (2021-03-30)

- Fix timespan formatting for content > 1h
- Try to fix invalid device encodings
- Rename `async_upnp_client.traffic` logger to `async_upnp_client.traffic.upnp` and add `async_upnp_client.traffic.ssdp` logger
- Added `DeviceUpdater` to support updating the `UpnpDevice` inline on changes to `BOOTID.UPNP.ORG`/`CONFIGID.UPNP.ORG`/`LOCATION`
- Added support for PAUSED_PLAYBACK state (#56, @brgerig)
- Add `DmrDevice.transport_state`, deprecate `DmrDevice.state`
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
- Less stricter version pinning of `python-didl-lite` (@fabaff)
- Drop Python 3.5 support, upgrade `pytest`/`pytest-asyncio`
- Convert type comments to annotations


0.14.14 (2020-04-25)

- Add support for fetching the serialNumber (@bdraco)


0.14.13 (2020-04-08)

- Expose `device_type` on `UpnpDevice` and `UpnpProfileDevice`


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

- Upgrade to python-didl-lite==1.2.2 for typing info, add `py.typed` marker
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
- Add work-around for win32-platform when using `upnp-client search`
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

- Add option to `upnp-client` to set timeout for device communication/discovery
- Add option to be strict (default false) with regard to invalid data
- Add more error handling to `upnp-client`
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

- Support old style `sendEvents`
- Add response-body when an error is received when calling an action
- Fixes to README
- Fixes to setup


0.9.0 (2018-03-18)

- Initial release
