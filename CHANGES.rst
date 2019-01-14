Changes
=======

0.14.0 (2019-01-14)

- Add __repr__ for UpnpAction.Argument and UPnpService.Action (@rytilahti)
- Support advertisements and rename discovery to search
- Use defusedxml to parse XML (@scop)
- Fix UpnpProfileDevice.async_search() + add UpnpProfileDevice.upnp_discover() for backwards compatiblity
- Add work-around for win32-platform when using `upnp-client search`
- Minor changes
- Typing fixes + automated type checking
- Support binding to IP(v4) for search and advertisements


0.13.8 (2018-12-29)

- Send content-type/charset on call-action, increasing compatiblity (@tsvi)


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
