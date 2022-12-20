Provide sync callbacks too, next to async callbacks.

By using sync callbacks, the number of tasks created is reduced. Async callbacks
are still supported, though some parameters are renamed to explicitly note the
callback is async.

Also, the lock in `SsdpDeviceTracker` is removed and thus is no longer a
`contextlib.AbstractAsyncContextManager`.
