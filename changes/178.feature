Avoid fetching time many times to purge devices (@bdraco)

Calling SsdpDevice.locations is now a KeysView and no longer has the side effect of purging stale locations. We now use the _timestamp that was injected into the headers to avoid fetching time again.
