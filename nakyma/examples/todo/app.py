"""A shared task list, the application the example films: each person opens /?who=<name>, every
page shows the same list and follows the others' changes.

    python app.py <port>
"""

import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Shared tasks</title>
<style>
  body { font: 16px system-ui, sans-serif; margin: 0; background: #f4f1ea; color: #2b2a27; }
  header { background: #2f5d50; color: #fff; padding: 14px 24px; font-size: 20px; }
  main { display: grid; grid-template-columns: 2fr 1fr; gap: 20px; padding: 20px 24px; }
  section { background: #fff; border-radius: 10px; padding: 16px 18px; box-shadow: 0 1px 3px #0002; }
  h2 { margin: 0 0 12px; font-size: 16px; color: #2f5d50; }
  form { display: flex; gap: 8px; margin-bottom: 12px; }
  input[type=text] { flex: 1; font: inherit; padding: 6px 10px; }
  button { font: inherit; padding: 6px 14px; background: #2f5d50; color: #fff; border: 0; border-radius: 6px; }
  ul { list-style: none; margin: 0; padding: 0; }
  li { padding: 8px 4px; border-bottom: 1px solid #eee; display: flex; gap: 10px; align-items: center; }
  li.done span.text { text-decoration: line-through; color: #999; }
  span.by { margin-left: auto; font-size: 13px; color: #888; }
  #count { font-size: 34px; font-weight: 700; color: #2f5d50; }
  #activity li { font-size: 14px; }
</style></head>
<body>
<header>Shared tasks · <b id="who"></b></header>
<main>
  <section id="list"><h2>Tasks</h2>
    <form id="add"><input id="text" type="text" placeholder="a new task" autocomplete="off"><button>Add</button></form>
    <ul id="items"></ul></section>
  <div>
    <section id="stats"><h2>Done</h2><div id="count">0 / 0</div></section>
    <section id="activity" style="margin-top:20px"><h2>Activity</h2><ul id="log"></ul></section>
  </div>
</main>
<script>
const who = new URLSearchParams(location.search).get('who') || 'someone';
document.getElementById('who').textContent = who;
const esc = s => s.replace(/[&<>"]/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
async function post(path, body) {
  await fetch(path, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({who, ...body})});
  refresh();
}
async function refresh() {
  const state = await (await fetch('/api/state')).json();
  document.getElementById('items').innerHTML = state.items.map(i =>
    `<li class="${i.done ? 'done' : ''}"><input type="checkbox" data-id="${i.id}" ${i.done ? 'checked' : ''}>
     <span class="text">${esc(i.text)}</span><span class="by">${esc(i.by)}</span></li>`).join('');
  const done = state.items.filter(i => i.done).length;
  document.getElementById('count').textContent = `${done} / ${state.items.length}`;
  document.getElementById('log').innerHTML = state.log.slice(-6).reverse().map(l => `<li>${esc(l)}</li>`).join('');
}
document.getElementById('add').onsubmit = e => {
  e.preventDefault();
  const input = document.getElementById('text');
  if (input.value.trim()) post('/api/add', {text: input.value.trim()});
  input.value = '';
};
document.getElementById('items').onchange = e => post('/api/done', {id: +e.target.dataset.id, done: e.target.checked});
refresh(); setInterval(refresh, 500);
</script></body></html>"""


class Tasks:
    def __init__(self):
        self.items, self.log, self.lock = [], [], threading.Lock()

    def add(self, who, text):
        with self.lock:
            self.items.append({"id": len(self.items), "text": text, "by": who, "done": False})
            self.log.append(f"{who} added “{text}”")

    def done(self, who, id, done):
        with self.lock:
            item = self.items[id]
            item["done"] = done
            self.log.append(f"{who} {'checked' if done else 'unchecked'} “{item['text']}”")

    def state(self):
        with self.lock:
            return {"items": list(self.items), "log": list(self.log)}


class Handler(BaseHTTPRequestHandler):
    tasks = Tasks()

    def log_message(self, *args):
        pass

    def send(self, body, content_type):
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        url = urlparse(self.path)
        if url.path == "/api/state":
            return self.send(json.dumps(self.tasks.state()).encode(), "application/json")
        self.send(PAGE.encode(), "text/html; charset=utf-8")

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        path = urlparse(self.path).path
        if path == "/api/add":
            self.tasks.add(body["who"], body["text"])
        elif path == "/api/done":
            self.tasks.done(body["who"], body["id"], body["done"])
        self.send(b"{}", "application/json")


if __name__ == "__main__":
    # the loopback only: an example, not a service
    ThreadingHTTPServer(("127.0.0.1", int(sys.argv[1])), Handler).serve_forever()
