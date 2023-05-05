Handle negative values for the bytes/traffic counters in IGDs.

Some IGDs implement the counters as i4 (4 byte integer) instead of
ui4 (unsigned 4 byte integer). This change tries to work around this by applying
an offset of `2**31`. To access the original value, use the variables with a
`_original` suffix.
