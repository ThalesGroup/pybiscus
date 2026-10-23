import hmac
import html
import os
import secrets
import urllib.parse
from pathlib import Path
from typing import Callable, Optional

from flask import Flask, g, jsonify, make_response, redirect, request

from pybiscus.session.csrf import HEADER

# A component listening beyond the loopback requires a token (on 127.0.0.1, with --require-token):
# the X-Pybiscus header stops other sites, not whoever reaches a port opened to the network.
# - access token: one per component (the manager's is its administration token), for its own
#   pages and actions; given once in the URL, then kept by the browser in a cookie
# - session token: the manager's, given to the participants; accepted by the manager on the
#   routes the agents and the runs call (registration, session parameters, webhooks)
# - an agent's invitation token: in place of the session token for one agent and its runs, tied
#   to the name and role the manager chose (pybiscus.session.invitations)
# - an agent's call token: made by the agent, given to the manager at its registration, which
#   presents it when it calls the agent (the manager keeps only the invitations' digests); a
#   client's run config posted to the server's agent is accepted once the manager vouches for the
#   client's token
SESSION_TOKEN_ENV = "PYBISCUS_SESSION_TOKEN"

TOKENS_DIR = Path(".pybiscus-cache/tokens")

LOCAL_HOSTS = ("localhost", "127.0.0.1", "::1")


def is_loopback(host: str) -> bool:
    return host in LOCAL_HOSTS or host.startswith("127.")


def tokens_required(host: str, require_token: bool) -> bool:
    return require_token or not is_loopback(host)


def _token_file(name: str) -> Path:
    return TOKENS_DIR / name


def component_token(name: str, given: Optional[str] = None) -> str:
    """the given token, or the one of the previous start, or a new one; kept in a file readable by
    its owner only, so that a restart does not log the browsers out"""

    path = _token_file(name)
    token = given
    if not token and path.is_file():
        token = path.read_text(encoding="utf-8").strip()
    if not token:
        token = secrets.token_urlsafe(24)
    if not path.is_file() or path.read_text(encoding="utf-8").strip() != token:
        TOKENS_DIR.mkdir(parents=True, exist_ok=True)
        path.touch(mode=0o600, exist_ok=True)
        path.chmod(0o600)
        path.write_text(token + "\n", encoding="utf-8")
    return token


def manager_token_names(port: int) -> tuple[str, str]:
    return f"manager-{port}-admin", f"manager-{port}-session"


def agent_token_name(port: int) -> str:
    return f"agent-{port}"


def session_token_for(url: Optional[str]) -> Optional[str]:
    """the session token to present to the manager at this URL: the environment's (set by the agent
    once registered, inherited by its runs), else, for a manager on this machine, its token file.
    Readable by the owner only, the file gives nothing that its reader could not already get: the
    local runs and agents need no copy of the token"""

    token = os.environ.get(SESSION_TOKEN_ENV)
    if token or not url:
        return token
    return local_manager_session_token(url)


def local_manager_session_token(url: str) -> Optional[str]:
    """the token file of the manager at this URL when it runs on this machine, started from the
    same directory"""
    parsed = urllib.parse.urlsplit(url)
    if parsed.hostname not in LOCAL_HOSTS or parsed.port is None:
        return None
    path = _token_file(manager_token_names(parsed.port)[1])
    return path.read_text(encoding="utf-8").strip() if path.is_file() else None


def set_session_token(token: Optional[str]) -> None:
    # through the environment: the runs the agent launches inherit it for their webhooks
    if token:
        os.environ[SESSION_TOKEN_ENV] = token
    else:
        os.environ.pop(SESSION_TOKEN_ENV, None)


def headers_for(url: Optional[str]) -> dict:
    headers = {HEADER: "1"}
    token = session_token_for(url)
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def session_access(view: Callable) -> Callable:
    """marks a route the other components call: the session token opens it too"""
    view.pybiscus_session_access = True
    return view


def invitation_access(view: Callable) -> Callable:
    """marks a route a lower-level manager calls: an invitation's token opens it too, and the route
    reads the invited bouquet in flask.g.invited_bouquet"""
    view.pybiscus_invitation_access = True
    return view


def invited_bouquet() -> Optional[str]:
    """the bouquet whose invitation the request presented, None otherwise"""
    return g.get("invited_bouquet")


def agent_access(view: Callable) -> Callable:
    """marks a route an agent or its runs call: an agent's invitation token opens it too, and the
    route reads the invited agent in flask.g.invited_agent"""
    view.pybiscus_agent_access = True
    return view


def invited_agent() -> Optional[dict]:
    """{"name", "role"} of the agent whose invitation the request presented, None otherwise"""
    return g.get("invited_agent")


def peer_access(view: Callable) -> Callable:
    """marks an agent's route another agent calls with its own token, which the manager vouches
    for (a client's run config posted to the server's agent): the session token alone no longer
    opens it, an invited client's name being reserved"""
    view.pybiscus_peer_access = True
    return view


def _same(offered: Optional[str], expected: Optional[str]) -> bool:
    return bool(offered and expected) and hmac.compare_digest(offered.encode(), expected.encode())


def _bearer() -> Optional[str]:
    scheme, _, value = request.headers.get("Authorization", "").partition(" ")
    return value.strip() if scheme.lower() == "bearer" else None


def _login_page(component: str) -> str:
    # the other parameters of the URL (presets of a config page) are kept through the form
    hidden = "".join(
        f'<input type="hidden" name="{html.escape(k)}" value="{html.escape(v)}">'
        for k, v in request.args.items(multi=True) if k != "token"
    )
    from pybiscus.session.theme import theme_head
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>Pybiscus {html.escape(component)}</title>
{theme_head()}
<style>body{{font-family:var(--sans);background:var(--bg);color:var(--text);display:flex;justify-content:center;padding-top:15vh}}
form{{background:var(--panel);border:1px solid var(--border);padding:2rem;border-radius:12px;max-width:34rem}}input{{width:100%;padding:.5rem;margin:.8rem 0;box-sizing:border-box}}
code{{color:var(--eval)}}</style></head><body><form method="get" action="{html.escape(request.path)}">
<h2>🔑 Pybiscus {html.escape(component)}: access token required</h2>
<p>Open the URL printed by the {html.escape(component)} when it started (it ends with <code>?token=…</code>),
or paste its token (also in <code>{html.escape(str(TOKENS_DIR))}/</code> where it was started).</p>
{hidden}<input type="password" name="token" autofocus placeholder="access token"><button type="submit">Open</button>
</form></body></html>"""


def _refuse_foreign_host(component: str):
    """without tokens, only a request naming the loopback. A site whose name an attacker re-points to
    127.0.0.1 (DNS rebinding) is the same origin as the component for the browser: it could add the
    X-Pybiscus header and read the answers. A reverse proxy passing its own name lands here too"""
    host = urllib.parse.urlsplit("//" + request.host).hostname or ""
    if is_loopback(host):
        return None
    message = (f"{component}: reached as '{request.host}', while it listens on the loopback without token "
               f"(a reverse proxy, or another site). To be reached under another name, start it with --require-token")
    if request.method == "GET" and "text/html" in request.headers.get("Accept", ""):
        return make_response(f"<!doctype html><meta charset='utf-8'><p>{html.escape(message)}</p>", 403)
    return jsonify({"error": message}), 403


def require_tokens(app: Flask, component: str, enabled: Callable[[], bool], cookie: Callable[[], str],
                   access_token: Callable[[], Optional[str]], session_token: Callable[[], Optional[str]],
                   invitation: Optional[Callable[[Optional[str]], Optional[str]]] = None,
                   invitation_problem: Optional[Callable[[Optional[str]], Optional[str]]] = None,
                   agent_invitation: Optional[Callable[[Optional[str]], Optional[dict]]] = None,
                   agent_invitation_problem: Optional[Callable[[Optional[str]], Optional[str]]] = None,
                   call_token: Optional[Callable[[], Optional[str]]] = None,
                   peer_check: Optional[Callable[[Optional[str]], bool]] = None) -> None:
    """the getters are read at each request: the tokens are known once the command line is parsed,
    and the session token of an agent once it is registered. invitation: the bouquet whose active
    invitation holds a token; agent_invitation: the agent whose one does; call_token: the one the
    manager presents to an agent; peer_check: whether the manager vouches for a peer's token"""

    @app.before_request
    def _check_tokens():
        # a CORS preflight never carries credentials; the request that follows it does
        if request.method == "OPTIONS" or request.endpoint == "static":
            return None
        view = app.view_functions.get(request.endpoint)
        # recognised even without tokens (on the loopback): the routes still tie the site to its bouquet
        if invitation is not None and getattr(view, "pybiscus_invitation_access", False):
            g.invited_bouquet = invitation(_bearer())
        if agent_invitation is not None and getattr(view, "pybiscus_agent_access", False):
            g.invited_agent = agent_invitation(_bearer())
        if not enabled():
            return _refuse_foreign_host(component)
        if g.get("invited_bouquet") or g.get("invited_agent"):
            return None

        access = access_token()
        offered_in_url = request.args.get("token")

        if _same(request.cookies.get(cookie()), access) or _same(_bearer(), access):
            return None

        if _same(offered_in_url, access):
            if request.method != "GET":
                return None
            # the token leaves the URL (history, Referer of the page's requests) for a cookie
            args = [(k, v) for k, v in request.args.items(multi=True) if k != "token"]
            target = request.path + ("?" + urllib.parse.urlencode(args) if args else "")
            response = redirect(target)
            response.set_cookie(cookie(), access, httponly=True, samesite="Lax", secure=request.is_secure)
            return response

        if getattr(view, "pybiscus_session_access", False):
            offered = (_bearer(), offered_in_url)
            if call_token is not None and any(_same(token, call_token()) for token in offered):
                return None
            if getattr(view, "pybiscus_peer_access", False) and peer_check is not None:
                if _bearer() and peer_check(_bearer()):
                    return None
            elif any(_same(token, session_token()) for token in offered):
                return None

        # a site or an agent whose invitation was revoked or expired is told so, not only that its token is wrong
        for problem_of, marker in ((invitation_problem, "pybiscus_invitation_access"),
                                   (agent_invitation_problem, "pybiscus_agent_access")):
            if problem_of is not None and getattr(view, marker, False):
                problem = problem_of(_bearer())
                if problem:
                    return jsonify({"error": f"{component}: {problem}"}), 401

        # "*/*" of fetch() would count as accepting HTML: only a page navigation names it
        if request.method == "GET" and "text/html" in request.headers.get("Accept", ""):
            return make_response(_login_page(component), 401)
        return jsonify({"error": f"{component}: a valid token is required (Authorization: Bearer <token>)"}), 401


def print_access(component: str, url: str, token: Optional[str]) -> None:
    # the only place where the operator gets the URL: printed whatever the logger configuration
    if token:
        print(f"🔑 {component}: open {url}?token={token}", flush=True)
    else:
        print(f"🔓 {component}: open {url} (no token required on the loopback; --require-token to require one)", flush=True)
