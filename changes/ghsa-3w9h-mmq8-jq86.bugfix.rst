**Prevent denial of service from malformed device descriptions (CWE-674)**

A deeply nested device description made ``DescriptionCache`` raise an unhandled
``RecursionError`` and left the description lookup for that location stuck, so
every later lookup of it hung forever. The same happened for descriptions with
an unexpected structure, descriptions rejected by defusedxml or containing
undecodable characters, and cancelled description fetches.

Such descriptions now resolve to ``None`` instead of raising, and a cancelled
fetch is no longer cached, so the next lookup retries it.
