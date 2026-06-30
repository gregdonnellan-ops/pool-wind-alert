import requests
import json
import os
import base64
from datetime import datetime, timezone, timedelta

# --- Config (must match check_wind.py) ---
NTFY_TOPIC = "plumewoodpoolumbrellas1234556"
MAX_ALERTS_PER_DAY = 3
PAUSE_HOURS = 6

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
REPO = os.environ.get("GITHUB_REPOSITORY", "")
STATE_FILE = "alert_state.json"

def get_state():
    url = f"https://api.github.com/repos/{REPO}/contents/{STATE_FILE}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    r = requests.get(url, headers=headers)
    if r.status_code == 200:
        data = r.json()
        content = base64.b64decode(data["content"]).decode("utf-8")
        state = json.loads(content)
        state["_sha"] = data["sha"]
        return state
    return {"date": "", "count": 0, "last_sent": None, "_sha": None}

def save_state(state):
    url = f"https://api.github.com/repos/{REPO}/contents/{STATE_FILE}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    sha = state.pop("_sha", None)
    content_b64 = base64.b64encode(json.dumps(state).encode()).decode()
    payload = {"message": "Update alert state [test]", "content": content_b64}
    if sha:
        payload["sha"] = sha
    r = requests.put(url, headers=headers, json=payload)
    return r.status_code

def should_send_alert(state, today):
    if state.get("date") != today:
        return True, "new_day"
    if state.get("count", 0) >= MAX_ALERTS_PER_DAY:
        return False, f"daily limit reached ({MAX_ALERTS_PER_DAY}/day)"
    last_sent = state.get("last_sent")
    if last_sent:
        last_dt = datetime.fromisoformat(last_sent)
        now_utc = datetime.now(timezone.utc)
        hours_since = (now_utc - last_dt).total_seconds() / 3600
        if hours_since < PAUSE_HOURS:
            return False, f"pause active ({hours_since:.1f}h elapsed, need {PAUSE_HOURS}h)"
    return True, "ok"

print("=" * 60)
print("TEST: Simulating 5 alert attempts")
print(f"Rules: max {MAX_ALERTS_PER_DAY}/day, {PAUSE_HOURS}h pause between batches")
print("=" * 60)

# Reset state to fresh for today so test always starts clean
today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
state = get_state()
# Force reset to today with 0 count so we start from scratch
state["date"] = today
state["count"] = 0
state["last_sent"] = None
status = save_state(state)
print(f"\nState reset to fresh (HTTP {status}). Starting test...\n")

sent = 0
blocked = 0

for attempt in range(1, 6):
    # Re-fetch state each iteration (simulates separate runs)
    state = get_state()
    ok, reason = should_send_alert(state, today)

    if ok:
        message = f"TEST alert #{attempt} — simulated wind alert"
        r = requests.post(
            f"https://ntfy.sh/{NTFY_TOPIC}",
            data=message.encode("utf-8"),
            headers={"Title": "Pool Umbrella Wind Alert [TEST]"}
        )
        print(f"Attempt {attempt}: ✅ SENT   — '{message}' (ntfy HTTP {r.status_code})")

        # Update state
        if state.get("date") != today:
            state["date"] = today
            state["count"] = 0
        state["count"] = state.get("count", 0) + 1
        # Simulate that 6+ hours have NOT passed — set last_sent to now
        state["last_sent"] = datetime.now(timezone.utc).isoformat()
        save_state(state)
        sent += 1
    else:
        print(f"Attempt {attempt}: 🚫 BLOCKED — {reason}")
        blocked += 1

print()
print("=" * 60)
print(f"RESULT: {sent} sent, {blocked} blocked")
print(f"Expected: 3 sent, 2 blocked")
if sent == 3 and blocked == 2:
    print("✅ TEST PASSED — rate limiting works correctly!")
else:
    print("❌ TEST FAILED — check logic above")
print("=" * 60)
