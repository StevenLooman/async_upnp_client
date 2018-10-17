Changes
=======

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
