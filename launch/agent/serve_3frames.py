"""Serves 3frames.html on the loopback, the origin the agents of launch/agent/cli allow to frame them
(--frame-ancestor): opened as a file, the page has no origin an agent could name."""

import argparse
import http.server
import pathlib

REPOSITORY = pathlib.Path(__file__).resolve().parents[2]
# these two only: the repository root also holds the components' tokens (.pybiscus-cache/tokens)
SERVED = {
    "/3frames.html": ("3frames.html", "text/html; charset=utf-8"),
    "/pybiscus/session/manager/static/pybiscus/js/bouquet_color.js":
        ("pybiscus/session/manager/static/pybiscus/js/bouquet_color.js", "text/javascript; charset=utf-8"),
}


class Handler(http.server.BaseHTTPRequestHandler):

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/":
            self.send_response(302)
            self.send_header("Location", "/3frames.html" + self.path[1:])
            self.end_headers()
            return
        if path not in SERVED:
            self.send_error(404)
            return
        file, content_type = SERVED[path]
        body = (REPOSITORY / file).read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        # the page frames the agents, nothing frames it
        self.send_header("Content-Security-Policy", "frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=5550)
    parser.add_argument("--query", default="", help="the page's parameters, as clients=3&mode=focus")
    args = parser.parse_args()
    server = http.server.ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    query = ("?" + args.query.lstrip("?")) if args.query else ""
    print(f"3frames.html: http://localhost:{args.port}/3frames.html{query}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
