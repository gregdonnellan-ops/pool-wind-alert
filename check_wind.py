import requests
import json
import os
import base64
from datetime import datetime, timezone

# --- Config ---
LAT = 30.437346
LON = -97.794689
WIND_THRESHOLD_MPH = 15
POOL_HOURS_START = 7
POOL_HOURS_END = 22
NTFY_TOPIC = "plumewoodpoolumbrellas1234556"
MAX_ALERTS_PER_DAY = 3
PAUSE_HOURS = 6

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
REPO = os.environ.get("GITHUB_REPOSITORY", "")
STATE_FILE = "alert_state.json"

# --- State helpers ---
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
    payload = {
        "message": "Update alert state",
        "content": content_b64,
    }
    if sha:
        payload["sha"] = sha
    requests.put(url, headers=headers, json=payload)

def should_send_alert(state, today):
    # Reset if new day
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

# --- Fetch wind data ---
url = (
    f"https://api.open-meteo.com/v1/forecast"
    f"?latitude={LAT}&longitude={LON}"
    f"&hourly=windspeed_10m,windgusts_10m"
    f"&temperature_unit=fahrenheit"
    f"&windspeed_unit=mph"
    f"&timezone=America/Chicago"
    f"&forecast_days=1"
)
response = requests.get(url)
data = response.json()

times = data["hourly"]["time"]
gusts = data["hourly"]["windgusts_10m"]
speeds = data["hourly"]["windspeed_10m"]

risky_hours = []
peak_gust = 0

for i, time_str in enumerate(times):
    hour = int(time_str.split("T")[1].split(":")[0])
    if POOL_HOURS_START <= hour < POOL_HOURS_END:
        gust = gusts[i]
        speed = speeds[i]
        if gust >= WIND_THRESHOLD_MPH or speed >= WIND_THRESHOLD_MPH:
            risky_hours.append(f"{hour}:00 — {gust} mph gusts")
        if gust > peak_gust:
            peak_gust = gust

if not risky_hours:
    print(f"All clear — peak gust only {peak_gust} mph during pool hours.")
else:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    state = get_state()
    ok, reason = should_send_alert(state, today)

    if ok:
        hours_text = ", ".join(risky_hours)
        message = f"⚠️ Keep umbrellas down! Peak gust: {peak_gust} mph. Risky hours: {hours_text}"
        requests.post(
            f"https://ntfy.sh/{NTFY_TOPIC}",
            data=message.encode("utf-8"),
            headers={"Title": "Pool Umbrella Wind Alert"}
        )
        print(f"Alert sent: {message}")

        # Update state
        if state.get("date") != today:
            state["date"] = today
            state["count"] = 0
        state["count"] = state.get("count", 0) + 1
        state["last_sent"] = datetime.now(timezone.utc).isoformat()
        save_state(state)
        print(f"State updated: {state['count']}/{MAX_ALERTS_PER_DAY} alerts today.")
    else:
        print(f"Alert suppressed: {reason}")
