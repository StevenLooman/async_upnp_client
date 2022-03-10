Don't raise parse errors if GET request returns an empty file.

Added an exception to client_factory.py to handle an empty XML document.
If XML document is invalid, scpd_el variable is replaced with a clean ElementTree.
