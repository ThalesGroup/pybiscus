import urllib.parse
from typing import Callable, Optional

from flask import Flask

from pybiscus.session.auth import LOCAL_HOSTS

# A page of another site could frame a component's pages and have its operator click under a
# decoy, or post messages to them: only the pages of their own origin and, for an agent, of the
# manager it registered with may frame them.


def _variants(scheme: str, hostname: str, port: Optional[int], loopback_names: bool) -> list:
    port_part = f":{port}" if port else ""
    hosts = [hostname] + ([h for h in LOCAL_HOSTS if h != hostname] if loopback_names else [])
    # CSP's host-source has no IPv6 literal: Chromium rejects http://[::1]:port with a console error
    return [f"{scheme}://{h}{port_part}" for h in hosts if ":" not in h]


def manager_origins(manager_url: Optional[str]) -> list:
    """the origins the manager's page may be opened under: its registered URL's, and the loopback's
    names on the same port (localhost and 127.0.0.1 are two origins for the browser)"""
    if not manager_url:
        return []
    parsed = urllib.parse.urlsplit(manager_url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return []
    return _variants(parsed.scheme, parsed.hostname, parsed.port, loopback_names=True)


def frame_ancestor_origins(origin: str) -> list:
    """an origin the operator allows to frame an agent (--frame-ancestor), with the loopback's other
    names when it is on the loopback; ValueError on anything but scheme://host[:port]"""
    parsed = urllib.parse.urlsplit(origin)
    # a path, a query or a wildcard would be read by the browser as another source, or as none
    if (parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.path not in ("", "/")
            or parsed.query or parsed.fragment or parsed.username or parsed.password or "*" in origin):
        raise ValueError(f"{origin!r}: an origin is expected, http(s)://host[:port]")
    return _variants(parsed.scheme, parsed.hostname, parsed.port, loopback_names=parsed.hostname in LOCAL_HOSTS)


def forbid_framing(app: Flask, allowed_origins: Callable[[], list] = lambda: []) -> None:

    @app.after_request
    def _frame_ancestors(response):
        origins = allowed_origins()
        response.headers["Content-Security-Policy"] = "frame-ancestors " + " ".join(["'self'", *origins])
        # older browsers: X-Frame-Options names no other origin
        if not origins:
            response.headers["X-Frame-Options"] = "SAMEORIGIN"
        return response
