import json
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from unittest import mock

import receiver

TOKEN = "secret"


class ReceiverTest(unittest.TestCase):
    def setUp(self):
        # Replace subprocess.run so no real command is ever executed.
        patcher = mock.patch.object(receiver.subprocess, "run")
        self.run = patcher.start()
        self.addCleanup(patcher.stop)

        config = receiver.Config(token=TOKEN, threshold=0.8, cooldown=3)
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), receiver.make_handler(config))
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"

    def post(self, body, token=TOKEN):
        headers = {"Content-Type": "application/json"}
        if token is not None:
            headers["X-EXS-Token"] = token
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        req = urllib.request.Request(self.url + "/api/command", data=data, headers=headers)
        try:
            with urllib.request.urlopen(req) as resp:
                return resp.status, json.load(resp)
        except urllib.error.HTTPError as err:
            return err.code, json.load(err)

    def test_health(self):
        with urllib.request.urlopen(self.url + "/health") as resp:
            self.assertEqual(json.load(resp), {"ok": True})

    def test_wrong_token(self):
        status, body = self.post({"label": "telegram", "confidence": 0.9}, token="nope")
        self.assertEqual(status, 401)
        self.assertFalse(body["ok"])
        self.run.assert_not_called()

    def test_missing_token(self):
        status, _ = self.post({"label": "telegram", "confidence": 0.9}, token=None)
        self.assertEqual(status, 401)
        self.run.assert_not_called()

    def test_executes_whitelisted_label(self):
        status, body = self.post({"label": "telegram", "confidence": 0.9})
        self.assertEqual(status, 200)
        self.assertEqual(body["action"], "telegram")
        self.assertEqual(self.run.call_args.args[0], ["open", "-a", "Telegram"])
        self.assertFalse(self.run.call_args.kwargs.get("shell", False))

    def test_below_threshold(self):
        status, body = self.post({"label": "telegram", "confidence": 0.5})
        self.assertEqual(status, 200)
        self.assertIsNone(body["action"])
        self.assertEqual(body["reason"], "below threshold")
        self.run.assert_not_called()

    def test_cooldown(self):
        self.post({"label": "slack", "confidence": 0.9})
        status, body = self.post({"label": "slack", "confidence": 0.9})
        self.assertEqual(status, 200)
        self.assertIsNone(body["action"])
        self.assertEqual(body["reason"], "cooldown")
        self.assertEqual(self.run.call_count, 1)

    def test_cooldown_is_per_label(self):
        self.post({"label": "slack", "confidence": 0.9})
        _, body = self.post({"label": "telegram", "confidence": 0.9})
        self.assertEqual(body["action"], "telegram")

    def test_unknown_label_rejected(self):
        for label in ("spotify", "__proto__", "rm -rf /"):
            status, body = self.post({"label": label, "confidence": 0.99})
            self.assertEqual(status, 400)
            self.assertFalse(body["ok"])
        self.run.assert_not_called()

    def test_noise_and_unknown_ignored(self):
        for label in ("noise", "unknown"):
            status, body = self.post({"label": label, "confidence": 0.99})
            self.assertEqual(status, 200)
            self.assertTrue(body["ok"])
            self.assertIsNone(body["action"])
        self.run.assert_not_called()

    def test_invalid_body(self):
        for body in (b"{oops", {"label": "telegram"}, {"label": "telegram", "confidence": 2}):
            status, _ = self.post(body)
            self.assertEqual(status, 400)
        self.run.assert_not_called()

    def test_focus_keeps_going_if_shortcut_missing(self):
        def fake_run(args, **kwargs):
            if args[0] == "shortcuts":
                raise receiver.subprocess.CalledProcessError(1, args)

        self.run.side_effect = fake_run
        status, body = self.post({"label": "focus", "confidence": 0.9})
        self.assertEqual(status, 200)
        self.assertEqual(body["action"], "focus")
        self.assertEqual([c.args[0][0] for c in self.run.call_args_list], ["osascript", "shortcuts"])


if __name__ == "__main__":
    unittest.main()
