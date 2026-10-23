#!/usr/bin/env python3
"""Hot-reload supervisor for Render.

Pulls project files from your Bot Panel, writes them to /app, runs the bot,
and restarts it within 2-3 seconds whenever a file changes in the panel or via CLI.
Also serves a lightweight HTTP /health server to satisfy Render Web Service requirements.
"""
import json, os, shlex, signal, subprocess, sys, time, urllib.request
from pathlib import Path

PANEL_URL = os.environ["PANEL_URL"].rstrip("/")
TOKEN = os.environ["PANEL_TOKEN"]
BOT_CMD = shlex.split(os.environ.get("BOT_CMD", "python -m src"))
APP_DIR = Path(os.environ.get("APP_DIR", "/app")).resolve()
POLL = float(os.environ.get("POLL_SECONDS", "3"))
STATE = APP_DIR / ".panel_state.json"


def call(action, **extra):
    body = json.dumps({"token": TOKEN, "action": action, **extra}).encode()
    req = urllib.request.Request(
        f"{PANEL_URL}/api/public/worker",
        data=body,
        headers={"content-type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read())
    if not data.get("ok"):
        raise RuntimeError(data.get("error"))
    return data["files"]


def load_state():
    try:
        return json.loads(STATE.read_text())
    except Exception:
        return {}


def sync(state):
    remote = {f["path"]: f["updated_at"] for f in call("manifest")}
    changed = [p for p, v in remote.items() if state.get(p) != v]
    removed = [p for p in state if p not in remote]
    
    # Download changed files in batches of 100
    for i in range(0, len(changed), 100):
        for f in call("files", paths=changed[i:i + 100]):
            target = (APP_DIR / f["path"]).resolve()
            if APP_DIR not in target.parents:
                continue  # refuse paths outside the app dir
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(f["content"])
            
    for p in removed:
        target = (APP_DIR / p).resolve()
        if APP_DIR in target.parents and target.exists():
            target.unlink()
            
    if changed or removed:
        STATE.write_text(json.dumps(remote))
    return remote, bool(changed or removed), changed + removed


def start():
    print(f"[runner] starting bot: {' '.join(BOT_CMD)}", flush=True)
    return subprocess.Popen(BOT_CMD, cwd=APP_DIR)


def stop(proc):
    if proc and proc.poll() is None:
        proc.send_signal(signal.SIGTERM)
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


def serve_health():
    """Render Web Services need an open $PORT; answer health checks there."""
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    class HealthHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("content-type", "text/plain")
            self.end_headers()
            self.wfile.write(b"ok")

        do_HEAD = do_GET

        def log_message(self, *a):
            pass

    port = int(os.environ.get("PORT", "10000"))
    srv = ThreadingHTTPServer(("0.0.0.0", port), HealthHandler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    print(f"[runner] health server active on port :{port}", flush=True)


def main():
    serve_health()
    APP_DIR.mkdir(parents=True, exist_ok=True)
    state, _, _ = sync(load_state())
    proc = start()
    signal.signal(signal.SIGTERM, lambda *_: (stop(proc), sys.exit(0)))

    while True:
        time.sleep(POLL)
        try:
            state, dirty, paths = sync(state)
        except Exception as e:
            print(f"[runner] sync failed: {e}", flush=True)
            continue
            
        if dirty:
            print(f"[runner] {len(paths)} file(s) changed, restarting bot: {paths[:5]}", flush=True)
            stop(proc)
            proc = start()
        elif proc.poll() is not None:
            print(f"[runner] bot exited ({proc.returncode}), restarting in 5s", flush=True)
            time.sleep(5)
            proc = start()


if __name__ == "__main__":
    main()
