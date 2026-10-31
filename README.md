# EXS

A microcontroller recognizes spoken keywords and sends them to a small
receiver on the Mac, which runs whitelisted desktop actions.

## model/
Python: create and evaluate the keyword-spotting model.

## firmware/
Arduino: runs on the board (microphone -> model -> HTTP request).

## server/
Python receiver (standard library only, Python 3). Runs on the Mac.

### Run

```
cd server
cp .env.example .env.local   # then fill in the values
python3 receiver.py
```

### Check with curl

```
curl http://localhost:3000/health

curl -X POST http://localhost:3000/api/command \
  -H "Content-Type: application/json" \
  -H "X-EXS-Token: <your token>" \
  -d '{"label": "telegram", "confidence": 0.95}'
```

A wrong or missing token gives `401`.

### Request

`POST /api/command` with header `X-EXS-Token` and JSON body:

```
{"label": "telegram", "confidence": 0.95}
```

- `label`: one of `telegram`, `elly`, `slack`, `focus`. `noise` and `unknown`
  are ignored. Any other label is rejected with `400`.
- `confidence`: number from 0 to 1.

Response: `{"ok": bool, "action": str|null, "reason": str}`.
`action` is the executed action, or `null` if nothing ran
(ignored, below threshold, cooldown).

### Environment variables (`server/.env.local`)

| Name | Default | Meaning |
|------|---------|---------|
| `EXS_TOKEN` | none (required) | Shared secret; must match the `X-EXS-Token` header. |
| `EXS_PORT` | `3000` | Port to listen on (all interfaces). |
| `EXS_THRESHOLD` | `0.8` | Minimum confidence to run an action. |
| `EXS_COOLDOWN` | `3` | Seconds before the same action can run again. |

Real environment variables override values in `.env.local`.

### Logs

One line per request, printed to the terminal and appended to
`server/logs/exs.log`: time, label, confidence, decision
(`executed` / `below threshold` / `cooldown` / `ignored` / `rejected`).

### Tests

```
cd server
python3 -m unittest test_receiver
```

### One-time macOS setup

The `focus` action runs a shortcut named exactly `exs focus on` that turns on
Do Not Disturb. Create it in the Shortcuts app. The first run also asks to
allow your terminal to control System Events (System Settings > Privacy &
Security > Automation).
