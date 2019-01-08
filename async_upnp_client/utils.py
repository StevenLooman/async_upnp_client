# -*- coding: utf-8 -*-
"""Utils for async_upnp_client."""

import re

from collections.abc import MutableMapping
from datetime import timedelta
from typing import Any, Dict, Generator, Mapping, Optional  # noqa: F401
from urllib.parse import urljoin


class CaseInsensitiveDict(MutableMapping):
    """Case insensitive dict."""

    def __init__(self, **kwargs: Any) -> None:
        """Initializer."""
        self._data = dict()  # type: Dict[str, Any]
        for key, value in kwargs.items():
            self[key] = value

    def _ci_key(self, key: str) -> str:
        """Get storable key from key."""
        # pylint: disable=no-self-use
        return key.lower()

    def __setitem__(self, key: str, value: Any) -> None:
        """Set item."""
        key_ci = self._ci_key(key)
        self._data[key_ci] = (key, value)

    def __getitem__(self, key: str) -> Any:
        """Get item."""
        ci_key = self._ci_key(key)
        return self._data[ci_key][1]

    def __delitem__(self, key: str) -> None:
        """Del item."""
        ci_key = self._ci_key(key)
        del self._data[ci_key]

    def __len__(self) -> int:
        """Get length."""
        return len(self._data)

    def __iter__(self) -> Generator[Any, None, None]:
        """Get iterator."""
        return (key for key, value in self._data.values())

    def __repr__(self) -> str:
        """Repr."""
        return str(dict(self.items()))

    def __eq__(self, other: Any) -> bool:
        """Compare for equality."""
        if not isinstance(other, Mapping):
            return NotImplemented

        dict_a = {self._ci_key(key): value for key, value in self.items()}
        dict_b = {self._ci_key(key): value for key, value in other.items()}
        return dict_a == dict_b

    def __hash__(self) -> int:
        """Get hash."""
        ci_dict = {self._ci_key(key): value for key, value in self.items()}
        return hash(tuple(sorted(ci_dict.items())))


def time_to_str(time: timedelta) -> str:
    """Convert timedelta to str/units."""
    total_seconds = abs(time.total_seconds())
    target = {
        'sign': '-' if time.total_seconds() < 0 else '',
        'hours': int(total_seconds // 3600),
        'minutes': int(total_seconds // 60),
        'seconds': int(total_seconds % 60),
    }
    return '{sign}{hours}:{minutes}:{seconds}'.format(**target)


def str_to_time(string: str) -> Optional[timedelta]:
    """Convert a string to timedelta."""
    regexp = r"(?P<sign>[-+])?(?P<h>\d+):(?P<m>\d+):(?P<s>\d+)\.?(?P<ms>\d+)?"
    match = re.match(regexp, string)
    if not match:
        return None

    sign = -1 if match.group('sign') == '-' else 1
    hours = int(match.group('h'))
    minutes = int(match.group('m'))
    seconds = int(match.group('s'))
    if match.group('ms'):
        msec = int(match.group('ms'))
    else:
        msec = 0
    return sign * timedelta(hours=hours, minutes=minutes, seconds=seconds, milliseconds=msec)


def absolute_url(device_url: str, url: str) -> str:
    """
    Convert a relative URL to an absolute URL pointing at device.

    If url is already an absolute url (i.e., starts with http:/https:),
    then the url itself is returned.
    """
    if url.startswith('http:') or \
       url.startswith('https:'):
        return url

    return urljoin(device_url, url)
