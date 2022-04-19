Include scope ID in link-local IPv6 host addresses (@chishm)

When determining the local IPv6 address used to connect to a remote host,
include the scope ID in the returned address string if using a link-local
IPv6 address.

This is needed to bind event listeners to the correct network interface.
