"""Real STDIO initialize/tools/browser smoke test, using a synthetic page only."""
import json
import os
from pathlib import Path
import queue
import shutil
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

browser = Path(os.environ["LOCALAPPDATA"]) / "ms-playwright/chromium-1248/chrome-win64/chrome.exe"
if not browser.exists():
    raise SystemExit("Install the documented Playwright browser first")
process = subprocess.Popen([shutil.which("npx.cmd"), "-y", "@playwright/mcp@0.0.83", "--headless", "--isolated",
                            "--executable-path", str(browser)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                           stderr=subprocess.DEVNULL, text=True, encoding="utf-8")
messages = queue.Queue()
def reader():
    for line in process.stdout:
        try:
            messages.put(json.loads(line))
        except json.JSONDecodeError:
            pass
threading.Thread(target=reader, daemon=True).start()

def call(identifier, method, params):
    process.stdin.write(json.dumps(dict(jsonrpc="2.0", id=identifier, method=method, params=params)) + "\n")
    process.stdin.flush()
    while True:
        message = messages.get(timeout=60)
        if message.get("id") == identifier:
            if "error" in message or message.get("result", {}).get("isError"):
                raise RuntimeError(json.dumps(message))
            return message["result"]

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"<h1>Synthetic environment check</h1>")
    def log_message(self, *args):
        pass
web = HTTPServer(("127.0.0.1", 0), Handler)
threading.Thread(target=web.serve_forever, daemon=True).start()
try:
    server = call(1, "initialize", dict(protocolVersion="2024-11-05", capabilities={}, clientInfo=dict(name="floodtwin-validation", version="0.1")))
    process.stdin.write(json.dumps(dict(jsonrpc="2.0", method="notifications/initialized")) + "\n")
    process.stdin.flush()
    listing = call(2, "tools/list", {})
    browser_result = call(3, "tools/call", dict(name="browser_navigate", arguments=dict(url=f"http://127.0.0.1:{web.server_port}")))
    browser_result = call(4, "tools/call", dict(name="browser_snapshot", arguments={}))
    result = dict(passed="Synthetic environment check" in json.dumps(browser_result), server=server["serverInfo"], tools=len(listing["tools"]), browser_roundtrip=True)
    Path("reports").mkdir(exist_ok=True)
    Path("reports/mcp-validation.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))
    if not result["passed"]:
        raise RuntimeError("Browser text assertion failed")
finally:
    web.shutdown()
    process.terminate()
