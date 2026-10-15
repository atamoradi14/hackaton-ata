"""MCP handshake + authenticated read-only identity check. Never reads token text."""
import json
from pathlib import Path
import subprocess
import threading
import queue
import sys

process = subprocess.Popen([sys.executable, str(Path("scripts/github-mcp.py").resolve())],
                           stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, encoding="utf-8")
messages = queue.Queue()
def read():
    for line in process.stdout:
        try:
            messages.put(json.loads(line))
        except json.JSONDecodeError:
            pass
threading.Thread(target=read, daemon=True).start()
def call(identifier, method, params):
    process.stdin.write(json.dumps(dict(jsonrpc="2.0", id=identifier, method=method, params=params)) + "\n")
    process.stdin.flush()
    while True:
        response = messages.get(timeout=60)
        if response.get("id") == identifier:
            if "error" in response or response.get("result", {}).get("isError"):
                raise RuntimeError("GitHub MCP request failed: " + json.dumps(response))
            return response["result"]
try:
    server = call(1, "initialize", dict(protocolVersion="2024-11-05", capabilities={}, clientInfo=dict(name="floodtwin-validation", version="0.1")))
    process.stdin.write(json.dumps(dict(jsonrpc="2.0", method="notifications/initialized")) + "\n")
    process.stdin.flush()
    listing = call(2, "tools/list", {})
    call(3, "tools/call", dict(name="get_me", arguments={}))
    result = dict(passed=True, authenticated_read=True, read_only=True, tools=len(listing["tools"]), server={k: server["serverInfo"][k] for k in ["name", "version"]})
    Path("reports/github-mcp-validation.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))
finally:
    process.terminate()
