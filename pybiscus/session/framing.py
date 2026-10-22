import urllib.parse
from typing import Callable, Optional

from flask import Flask

from pybiscus.session.auth import LOCAL_HOSTS

# A page of another site could frame a component's pages and have its operator click under a
# decoy, or post messages to them: only the pages of their own origin and, for an agent, of the
# manager it registered with may frame them.


def manager_origins(manager_url: Optional[str]) -> list:
    """the origins the manager's page may be opened under: its registered URL's, and the loopback's
    names on the same port (localhost, 127.0.0.1 and [::1] are three origins for the browser)"""
    if not manager_url:
        return []
    parsed = urllib.parse.urlsplit(manager_url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return []
    port = f":{parsed.port}" if parsed.port else ""
    hosts = [parsed.hostname] + [h for h in LOCAL_HOSTS if h != parsed.hostname]
    return [f"{parsed.scheme}://{'[' + h + ']' if ':' in h else h}{port}" for h in hosts]


def forbid_framing(app: Flask, allowed_origins: Callable[[], list] = lambda: []) -> None:

    @app.after_request
    def _frame_ancestors(response):
        origins = allowed_origins()
        response.headers["Content-Security-Policy"] = "frame-ancestors " + " ".join(["'self'", *origins])
        # older browsers: X-Frame-Options names no other origin
        if not origins:
            response.headers["X-Frame-Options"] = "SAMEORIGIN"
        return response
