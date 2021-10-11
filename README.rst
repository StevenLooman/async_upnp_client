Async UPnP Client
=================

Asyncio UPnP Client library for Python/asyncio.

Written initially for use in `Home Assistant <https://github.com/home-assistant/home-assistant>`_ to drive `DLNA DMR`-capable devices, but useful for other projects as well.

Status
------

.. image:: https://img.shields.io/travis/StevenLooman/async_upnp_client.svg
   :target: https://app.travis-ci.com/github/StevenLooman/async_upnp_client

.. image:: https://img.shields.io/pypi/v/async_upnp_client.svg
   :target: https://pypi.python.org/pypi/async_upnp_client

.. image:: https://img.shields.io/pypi/format/async_upnp_client.svg
   :target: https://pypi.python.org/pypi/async_upnp_client

.. image:: https://img.shields.io/pypi/pyversions/async_upnp_client.svg
   :target: https://pypi.python.org/pypi/async_upnp_client

.. image:: https://img.shields.io/pypi/l/async_upnp_client.svg
   :target: https://pypi.python.org/pypi/async_upnp_client


General set up
--------------

The `UPnP Device Architecture <https://openconnectivity.org/upnp-specs/UPnP-arch-DeviceArchitecture-v2.0-20200417.pdf>`_ document contains several sections describing different parts of the UPnP standard. These chapters/sections can mostly be mapped to the following modules:

* Chapter 1 Discovery
   * Section 1.1 SSDP: `async_upnp_client.ssdp`
   * Section 1.2 Advertisement: `async_upnp_client.advertisement` provides basic functionality to receive advertisements.
   * Section 1.3 Search: `async_upnp_client.search` provides basic functionality to do search requests and gather the responses.
   * `async_upnp_client.ssdp_client` contains the `SsdpListener` which combines advertisements and search to get the known devices and provides callbacks on changes. It is meant as something which runs continuously to provide useful information about the SSDP-active devices.
* Chapter 2 Description / Chapter 3 Control
   * `async_upnp_client.client_factory`/`async_upnp_client.client` provide a series of classes to get information about the device/services using the 'description', and interact with these devices.
* Chapter 4 Eventing
   * `async_upnp_client.event_handler` provides functionality to handle events received from the device.

There are several 'profiles' which a device can implement to provide a standard interface to talk to. Some of these profiles are added to this library. The following profiles are currently available:

* Internet Gateway Device (IGD)
   * `async_upnp_client.profiles.igd`
* Digital Living Network Alliance (DLNA)
   * `async_upnp_client.profiles.dlna`
* Printers
   * `async_upnp_client.profiles.printer`

For examples on how to use `async_upnp_client`, see `examples`/ .

Note that this library is most likely does not fully implement all functionality from the UPnP Device Architecture document and/or contains errors/bugs/mis-interpretations.


Contributing
------------

See `CONTRIBUTING.rst`.


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
- Update `setup.py` and `CHANGES.rst` to set version and commit: `git add setup.py CHANGES.rst && git commit -m "Releasing <version>"`
- Tag release: `git tag <version>`
- Checkout tag: `git checkout <version>`
- Build: `rm -rf build dist && python setup.py build sdist`
- Upload using twine: `twine upload dist/*`
- Switch to development: `git checkout development`
- Merge master to development: `git merge master`
- Update `setup.py` and `CHANGES.rst` to set version and commit `git add setup.py CHANGES.rst && git commit -m "Continuing development"`
- Push to github: `git push --all && git push --tags`


Profiling
---------

To do profiling it is recommended to install `pytest-profiling <https://pypi.org/project/pytest-profiling>`_. Then run a test with profiling enabled, and write the results to a graph::

    # Run tests with profiling and svg-output enabled. This will generate `prof/*.prof` files, and a svg file.
    $ pytest --profile-svg -k test_case_insensitive_dict_profile
    ...

    # Open generated SVG file.
    $ xdg-open prof/combined.svg


Alternatively, you can generate a profiling data file, use `pyprof2calltree <https://github.com/pwaller/pyprof2calltree/>_` to convert the data and open `kcachegrind <http://kcachegrind.sourceforge.net/html/Home.html>`_. For example:

    # Run tests with profiling enabled, this will generate `prof/*.prof` files.
    $ pytest --profile -k test_case_insensitive_dict_profile
    ...

    $ pyprof2calltree -i prof/combined.prof -k
    launching kcachegrind


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
