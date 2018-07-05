Changes
=======

0.11.2 (2018-07-05)

- Fix log message


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
