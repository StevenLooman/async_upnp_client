Async UPnP Client
=================

Asyncio UPnP Client library for Python/asyncio.

Written initially for use in `Home Assistant <https://github.com/home-assistant/home-assistant>`_ to drive `DLNA DMR`-capable devices, but useful for other projects as well.

Status
------

.. image:: https://img.shields.io/travis/StevenLooman/async_upnp_client.svg
   :target: https://travis-ci.org/StevenLooman/async_upnp_client/branches

.. image:: https://img.shields.io/pypi/v/async_upnp_client.svg
   :target: https://pypi.python.org/pypi/async_upnp_client

.. image:: https://img.shields.io/pypi/format/async_upnp_client.svg
   :target: https://pypi.python.org/pypi/async_upnp_client

.. image:: https://img.shields.io/pypi/pyversions/async_upnp_client.svg
   :target: https://pypi.python.org/pypi/async_upnp_client

.. image:: https://img.shields.io/pypi/l/async_upnp_client.svg
   :target: https://pypi.python.org/pypi/async_upnp_client


Contributing
------------

If you wish to contribute to `async_upnp_client`, then thank you! You can create a create a pull request with your changes.

Please do add your change the the `CHANGES.rst` file, one line per change, with your Github username added.


Usage
-----

See `examples/` for examples on how to use async_upnp_client.


upnp-client
-----------

A command line interface is provided via the `upnp-client` script. This script can be used to:

- call an action
- subscribe to services and listen for events
- show UPnP traffic (--debug-traffic) from and to the device
- show pretty printed JSON (--pprint) for human readability
- discover devices

The output of the script is a single line of JSON for each action-call or subscription-event. See the programs help for more information.

An example of calling an action::

    $ upnp-client --pprint call-action http://192.168.178.10:49152/description.xml RC/GetVolume InstanceID=0 Channel=Master
    {
        "timestamp": 1531482271.5603056,
        "service_id": "urn:upnp-org:serviceId:RenderingControl",
        "service_type": "urn:schemas-upnp-org:service:RenderingControl:1",
        "action": "GetVolume",
        "in_parameters": {
            "InstanceID": 0,
            "Channel": "Master"
        },
        "out_parameters": {
            "CurrentVolume": 70
        }
    }


An example of subscribing to all services, note that the program stays running until you stop it (ctrl-c)::

    $ upnp-client --pprint subscribe http://192.168.178.10:49152/description.xml \*
    {
        "timestamp": 1531482518.3663802,
        "service_id": "urn:upnp-org:serviceId:RenderingControl",
        "service_type": "urn:schemas-upnp-org:service:RenderingControl:1",
        "state_variables": {
            "LastChange": "<Event xmlns=\"urn:schemas-upnp-org:metadata-1-0/AVT_RCS\">\n<InstanceID val=\"0\">\n<Mute channel=\"Master\" val=\"0\"/>\n<Volume channel=\"Master\" val=\"70\"/>\n</InstanceID>\n</Event>\n"
        }
    }
    {
        "timestamp": 1531482518.366804,
        "service_id": "urn:upnp-org:serviceId:RenderingControl",
        "service_type": "urn:schemas-upnp-org:service:RenderingControl:1",
        "state_variables": {
            "Mute": false,
            "Volume": 70
        }
    }
    ...

You can subscribe to list of services by providing these names or abbreviated names, such as::

    $ upnp-client --pprint subscribe http://192.168.178.10:49152/description.xml RC AVTransport


An example of discovering devices::

    $ upnp-client --pprint discover
    {
        "cache-control": "max-age=3600",
        "date": "Sat, 27 Oct 2018 10:43:42 GMT",
        "ext": "",
        "location": "http://192.168.178.1:49152/description.xml",
        "opt": "\"http://schemas.upnp.org/upnp/1/0/\"; ns=01",
        "01-nls": "906ad736-cfc4-11e8-9c22-8bb67c653324",
        "server": "Linux/4.14.26+, UPnP/1.0, Portable SDK for UPnP devices/1.6.20.jfd5",
        "x-user-agent": "redsonic",
        "st": "upnp:rootdevice",
        "usn": "uuid:e3a17dd5-9d85-3131-3c34-b827eb498d72::upnp:rootdevice",
        "_timestamp": "2018-10-27 12:43:09.125408"
    }



Abstractions
------------

- `DLNA Digital Media Renderer` (DLNA DMR) devices
  - Primarily built for use with `Home Assistant <https://github.com/home-assistant/home-assistant>`_, but might be useful in other projects too.
- `Internet Gateway Devices` (IGD)
- Printers
