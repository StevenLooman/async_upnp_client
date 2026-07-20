**Guard against SSRF from rogue UPnP devices (CWE-918)**

Service ``controlURL``, ``SCPDURL`` and ``eventSubURL`` values are now validated
before use: a value that resolves to a different host than the device
description URL, or that is malformed, is refused. Per UDA 1.1/2.0 these
elements must be relative to the description URL, so conformant devices are
unaffected. In strict mode a ``UpnpError`` is raised; in non-strict mode (used
by Home Assistant) the offending service is skipped with a warning, so a device
serving such URLs now exposes fewer (or no) services rather than being created
with cross-host URLs.

In addition, ``is_valid_location`` now validates discovery locations using
proper URL/IP parsing instead of substring matching. Loopback, unspecified and
IPv4 link-local (cloud-metadata) addresses can no longer be reached via
obfuscated forms — decimal, octal, hex, IPv4-mapped IPv6, percent-encoded, or
credentials in the authority — and malformed locations are rejected rather than
raising.

This is best-effort defence-in-depth, not a security boundary: a hostname that
resolves to such an address is still allowed, since the UPnP specification
permits hostnames in URLs and they cannot be distinguished from legitimate
device names at parse time. Hostname-based SSRF can only be caught by validating
the resolved address at connect time.
