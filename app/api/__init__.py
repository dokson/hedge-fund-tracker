"""
HTTP API routers (in addition to the legacy ones still in app/server.py).

New endpoints land in submodules of this package and are wired via
`include_routers_for_api()` from `app.server`. Eventually the legacy routes
in `app/server.py` migrate here too.
"""
