"""Setup."""

import os.path

from setuptools import setup

here = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(here, "README.rst"), encoding="utf-8") as f:
    LONG_DESCRIPTION = f.read()


PACKAGES = (
    "async_upnp_client",
    "async_upnp_client.profiles",
)


INSTALL_REQUIRES = [
    "voluptuous >= 0.12.1",
    "aiohttp >= 3.7.4",
    "async-timeout >=3.0, <5.0",
    "python-didl-lite ~= 1.3.2",
    "defusedxml >= 0.6.0",
]


TEST_REQUIRES = [
    "pytest ~= 6.2.4",
    "pytest-asyncio ~= 0.15.1",
    "pytest-cov ~= 2.12.1",
    "coverage ~= 5.5",
    "asyncmock ~= 0.4.2",
]


setup(
    name="async_upnp_client",
    version="0.23.4",
    description="Async UPnP Client",
    long_description=LONG_DESCRIPTION,
    url="https://github.com/StevenLooman/async_upnp_client",
    author="Steven Looman",
    author_email="steven.looman@gmail.com",
    license="http://www.apache.org/licenses/LICENSE-2.0",
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: Apache Software License",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
    ],
    packages=PACKAGES,
    package_data={
        "async_upnp_client": ["py.typed"],
    },
    install_requires=INSTALL_REQUIRES,
    tests_require=TEST_REQUIRES,
    entry_points={"console_scripts": ["upnp-client=async_upnp_client.cli:main"]},
)
