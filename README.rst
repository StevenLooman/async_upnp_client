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

The output of the script is a single line of JSON for each action-call or subscription-event. See the programs help for more information.

An example of calling an action::

    $ upnp-client --device http://192.168.178.10:49152/description.xml --pprint call-action RC/GetVolume InstanceID=0 Channel=Master
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


An example of subscribing to a service, note that the program stays running until you stop it (ctrl-c)::

    $ upnp-client --device http://192.168.178.10:49152/description.xml --pprint subscribe --bind 192.168.178.72 RC
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


Abstractions
------------

- `DLNA Digital Media Renderer` (DLNA DMR) devices
  - Primarily built for use with `Home Assistant <https://github.com/home-assistant/home-assistant>`, but might be useful in other projects too.
- `Internet Gateway Devices` (IGD)
- Printers
