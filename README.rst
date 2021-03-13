Async UPnP Client
=================

Asyncio UPnP Client library for Python/asyncio.

Written initially for use in `Home Assistant <https://github.com/home-assistant/home-assistant>`_ to drive `DLNA DMR`-capable devices, but useful for other projects as well.

Status
------

.. image:: https://img.shields.io/travis/StevenLooman/async_upnp_client.svg
   :target: https://travis-ci.com/StevenLooman/async_upnp_client/branches

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

See `CONTRIBUTING.rst`.


Usage
-----

See `examples/` for examples on how to use async_upnp_client.


Development
-----------

Development is done on the `development` branch.

`pre-commit` is used to run several checks before committing. You can install `pre-commit` and the git-hook by doing::

    $ pip install pre-commit
    $ pre-commit --install


Releasing
---------

Steps for releasing:

- Switch to master: `git checkout master`
- Merge development to master: `git merge development`
- Update `setup.py` to set version and commit: `git add setup.py && git commit -m "Releasing <version>"`
- Tag release: `git tag <version>`
- Checkout tag: `git checkout <version>`
- Build: `rm -rf build dist && python setup.py build sdist`
- Upload using twine: `twine upload dist/*`
- Switch to development: `git checkout development`
- Merge master to development: `git merge master`
- Update `setup.py` to set version and commit `git add setup.py && git commit -m "Continuing development"`
- Push to github: `git push --all && git push --tags`


upnp-client
-----------

A command line interface is provided via the `upnp-client` script. This script can be used to:

- call an action
- subscribe to services and listen for events
- show UPnP traffic (--debug-traffic) from and to the device
- show pretty printed JSON (--pprint) for human readability
- search for devices
- listen for advertisements

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


An example of searching for devices::

    $ upnp-client --pprint search
    {
        "Cache-Control": "max-age=3600",
        "Date": "Sat, 27 Oct 2018 10:43:42 GMT",
        "EXT": "",
        "Location": "http://192.168.178.1:49152/description.xml",
        "OPT": "\"http://schemas.upnp.org/upnp/1/0/\"; ns=01",
        "01-NLS": "906ad736-cfc4-11e8-9c22-8bb67c653324",
        "Server": "Linux/4.14.26+, UPnP/1.0, Portable SDK for UPnP devices/1.6.20.jfd5",
        "X-User-Agent": "redsonic",
        "ST": "upnp:rootdevice",
        "USN": "uuid:e3a17dd5-9d85-3131-3c34-b827eb498d72::upnp:rootdevice",
        "_timestamp": "2018-10-27 12:43:09.125408",
        "_host": "192.168.178.1",
        "_port": 49152
        "_udn": "uuid:e3a17dd5-9d85-3131-3c34-b827eb498d72",
        "_source": "search"
    }


An example of listening for advertisements, note that the program stays running until you stop it (ctrl-c)::

    $ upnp-client --pprint advertisements
    {
        "Host": "239.255.255.250:1900",
        "Cache-Control": "max-age=30",
        "Location": "http://192.168.178.1:1900/WFADevice.xml",
        "NTS": "ssdp:alive",
        "Server": "POSIX, UPnP/1.0 UPnP Stack/2013.4.3.0",
        "NT": "urn:schemas-wifialliance-org:device:WFADevice:1",
        "USN": "uuid:99cb221c-1f15-c620-dc29-395f415623c6::urn:schemas-wifialliance-org:device:WFADevice:1",
        "_timestamp": "2018-12-23 11:22:47.154293",
        "_host": "192.168.178.1",
        "_port": 1900
        "_udn": "uuid:99cb221c-1f15-c620-dc29-395f415623c6",
        "_source": "advertisement"
    }



Abstractions
------------

- `DLNA Digital Media Renderer` (DLNA DMR) devices
  - Primarily built for use with `Home Assistant <https://github.com/home-assistant/home-assistant>`_, but might be useful in other projects too.
- `Internet Gateway Devices` (IGD)
- Printers
