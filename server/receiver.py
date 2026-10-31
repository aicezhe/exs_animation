#!/usr/bin/env python3
"""Minimal EXS command receiver (standard library only).

The board POSTs {"label": str, "confidence": float} to /api/command.
Only whitelisted labels run a fixed macOS command; nothing from the
request ever reaches a command line (the label is only a dict key).
"""

import hmac
import json
import logging
import math
import os
import subprocess
import threading
import time
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

SERVER_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_PATH = os.path.join(SERVER_DIR, "logs", "exs.log")
ENV_PATH = os.path.join(SERVER_DIR, ".env.local")

ACTION_TIMEOUT = 10  # seconds
MAX_BODY = 4096  # bytes

# Hides (not quits) every visible foreground app except VS Code and Safari.
HIDE_OTHERS_SCRIPT = """
tell application "System Events"
  set visible of (every application process whose visible is true and background only is false and name is not "Code" and name is not "Safari") to false
end tell
"""

# Labels that never trigger anything.
IGNORED_LABELS = frozenset({"noise", "unknown"})

log = logging.getLogger("exs")


def _run(args):
    """Run a fixed argument list: no shell, with a timeout."""
    subprocess.run(args, check=True, timeout=ACTION_TIMEOUT)


def _open_app(name):
    return lambda: _run(["open", "-a", name])


def _open_elly():
    _run(["open", "https://elly2026.didattica.unipr.it/my/courses.php"])


def _focus():
    _run(["osascript", "-e", HIDE_OTHERS_SCRIPT])
    # A missing shortcut is logged but does not undo the step above.
    try:
        _run(["shortcuts", "run", "exs focus on"])
    except Exception as exc:
        log.error('focus: shortcut "exs focus on" failed: %s', exc)


# Fixed whitelist: label -> function that runs the action.
ACTIONS = {
    "telegram": _open_app("Telegram"),
    "elly": _open_elly,
    "slack": _open_app("Slack"),
    "focus": _focus,
}


@dataclass
class Config:
    token: str
    threshold: float = 0.8
    cooldown: float = 3.0


def load_env_file(path):
    """Load KEY=VALUE lines into os.environ; real environment variables win."""
    try:
        with open(path, encoding="utf-8") as f:
            lines = f.read().splitlines()
    except FileNotFoundError:
        return
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip().strip("\"'")
        if value:
            os.environ.setdefault(key.strip(), value)


def config_from_env():
    return Config(
        token=os.environ.get("EXS_TOKEN", ""),
        threshold=float(os.environ.get("EXS_THRESHOLD", "0.8")),
        cooldown=float(os.environ.get("EXS_COOLDOWN", "3")),
    )


def setup_logging():
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(message)s",
        handlers=[logging.StreamHandler(), logging.FileHandler(LOG_PATH, encoding="utf-8")],
    )


def make_handler(config):
    last_run = {}  # label -> time.monotonic() of the last run
    lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def _send(self, status, ok, action, reason):
            body = json.dumps({"ok": ok, "action": action, "reason": reason}).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _decide(self, label, confidence, decision, status, ok, action, reason):
            log.info("label=%s confidence=%s decision=%s", label, confidence, decision)
            self._send(status, ok, action, reason)

        def do_GET(self):
            if self.path == "/health":
                body = b'{"ok": true}'
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            else:
                self._send(404, False, None, "not found")

        def do_POST(self):
            if self.path != "/api/command":
                self._send(404, False, None, "not found")
                return

            # Without a configured token every request is refused.
            given = self.headers.get("X-EXS-Token", "")
            if not config.token or not hmac.compare_digest(given.encode(), config.token.encode()):
                self._decide("-", "-", "rejected", 401, False, None, "unauthorized")
                return

            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= MAX_BODY:
                    raise ValueError("bad length")
                data = json.loads(self.rfile.read(length))
                label = data["label"]
                confidence = data["confidence"]
                if (
                    not isinstance(label, str)
                    or isinstance(confidence, bool)
                    or not isinstance(confidence, (int, float))
                    or not math.isfinite(confidence)
                    or not 0 <= confidence <= 1
                ):
                    raise ValueError("bad fields")
            except (ValueError, KeyError, TypeError):
                self._decide("-", "-", "rejected", 400, False, None, "invalid request")
                return

            if label in IGNORED_LABELS:
                self._decide(label, confidence, "ignored", 200, True, None, "ignored")
                return
            if label not in ACTIONS:
                self._decide(label, confidence, "rejected", 400, False, None, "label not allowed")
                return
            if confidence < config.threshold:
                self._decide(label, confidence, "below threshold", 200, True, None, "below threshold")
                return

            with lock:
                now = time.monotonic()
                if label in last_run and now - last_run[label] < config.cooldown:
                    in_cooldown = True
                else:
                    in_cooldown = False
                    # Set before running so two quick requests cannot both pass.
                    last_run[label] = now
            if in_cooldown:
                self._decide(label, confidence, "cooldown", 200, True, None, "cooldown")
                return

            try:
                ACTIONS[label]()
            except Exception as exc:
                log.error("action %s failed: %s", label, exc)
                self._decide(label, confidence, "error", 500, False, label, "action failed")
                return
            self._decide(label, confidence, "executed", 200, True, label, "executed")

        def log_message(self, *args):
            pass  # we write our own one-line-per-request log

    return Handler


def main():
    load_env_file(ENV_PATH)
    config = config_from_env()
    setup_logging()
    if not config.token:
        log.warning("EXS_TOKEN is not set: every command request will get 401")
    port = int(os.environ.get("EXS_PORT", "3000"))
    server = ThreadingHTTPServer(("0.0.0.0", port), make_handler(config))
    log.info("listening on 0.0.0.0:%d", port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
