import sys

import os.path

from setuptools import setup
from setuptools.command.test import test as TestCommand


class PyTest(TestCommand):
    def finalize_options(self):
        TestCommand.finalize_options(self)
        self.test_args = [
            '--strict',
            '--verbose',
            '--tb=long',
            'tests']
        self.test_suite = True

    def run_tests(self):
        import pytest
        errcode = pytest.main(self.test_args)
        sys.exit(errcode)


here = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(here, 'README.rst'), encoding='utf-8') as f:
    LONG_DESCRIPTION = f.read()


INSTALL_REQUIRES=[
    'voluptuous>=0.11.1',
    'aiohttp>=3.3.2',
    'async-timeout>=3.0.0',
    'python-didl-lite==1.1.0',
]


TEST_REQUIRES=[
    'pytest',
    'pytest-asyncio',
]


setup(
    name='async_upnp_client',
    version='0.12.7',
    description='Async UPnP Client',
    long_description=LONG_DESCRIPTION,
    url='https://github.com/StevenLooman/async_upnp_client',
    author='Steven Looman',
    author_email='steven.looman@gmail.com',
    license='http://www.apache.org/licenses/LICENSE-2.0',
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: Apache Software License',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
    ],
    packages=['async_upnp_client'],
    install_requires=INSTALL_REQUIRES,
    tests_require=TEST_REQUIRES,
    cmdclass={'test': PyTest},
    entry_points={
        'console_scripts': ['upnp-client=async_upnp_client.cli:main']
    },
)
