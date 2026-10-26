"""The web server of the manager and of the agents: cheroot by default, Werkzeug's development server
with --debug (its reloader and in-browser debugger exist only there)."""

import ssl
import sys
import threading
from typing import Optional

from flask import Flask

# a thread per request in progress: an open run monitor (server-sent events) holds one for as long as
# it stays open, and cheroot's pool does not grow; idle keep-alive connections hold none
THREADS = 64
# seconds a read or a write may block: a client that stops reading a stream is dropped after it
SOCKET_TIMEOUT = 30
# seconds given at Ctrl+C to the requests in progress; the streams never end, they are abandoned
SHUTDOWN_TIMEOUT = 2


def _peer_went_away(error: Optional[BaseException]) -> bool:
    while error is not None:
        if isinstance(error, (ssl.SSLEOFError, ConnectionResetError, BrokenPipeError)) \
                or "UNEXPECTED_EOF" in str(error):
            return True
        error = error.__context__
    return False


def _server_class():
    from cheroot import wsgi

    class Server(wsgi.Server):
        def error_log(self, msg="", level=20, traceback=False):
            # a browser or requests closing an idle HTTPS connection without TLS's close_notify:
            # cheroot logs it with a traceback, in the agents' logs the operators read
            if not _peer_went_away(sys.exc_info()[1]):
                super().error_log(msg, level, traceback)

    return Server


def serve(app: Flask, host: str, port: int, ssl_context: Optional[tuple] = None, debug: bool = False) -> None:
    if debug:
        app.run(debug=True, host=host, port=port, ssl_context=ssl_context)
        return

    server = _server_class()((host, port), app, numthreads=THREADS, timeout=SOCKET_TIMEOUT,
                         shutdown_timeout=SHUTDOWN_TIMEOUT, server_name=app.import_name)
    if ssl_context:
        from cheroot.ssl.builtin import BuiltinSSLAdapter
        server.ssl_adapter = BuiltinSSLAdapter(*ssl_context)

    failure = []

    def run():
        try:
            server.safe_start()
        except BaseException as error:
            failure.append(error)

    # started from a daemon thread, cheroot's workers are daemons too: at exit Python abandons them,
    # as it did Werkzeug's, instead of waiting forever for an open run monitor's stream (cheroot's
    # stop joins every worker after its timeout)
    serving = threading.Thread(target=run, name="web-server", daemon=True)
    serving.start()
    try:
        while serving.is_alive():
            serving.join(0.5)
    except KeyboardInterrupt:
        # Werkzeug ended quietly on Ctrl+C; the atexit handlers (recording, links) run after this
        stopping = threading.Thread(target=server.stop, daemon=True)
        stopping.start()
        stopping.join(SHUTDOWN_TIMEOUT + 1)
        return
    if failure:
        # the port already taken, a certificate unreadable: the process must fail as it did
        raise failure[0]
