import requests

LAT = 30.437346
LON = -97.794689
WIND_THRESHOLD_MPH = 15
POOL_HOURS_START = 7
POOL_HOURS_END = 22
NTFY_TOPIC = "plumewoodpoolumbrellas1234556"

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

if risky_hours:
    hours_text = ", ".join(risky_hours)
    message = f"⚠️ Keep umbrellas down today! Peak gust: {peak_gust} mph. Risky hours: {hours_text}"
    requests.post(
        f"https://ntfy.sh/{NTFY_TOPIC}",
        data=message.encode("utf-8"),
        headers={"Title": "Pool Umbrella Wind Alert"}
    )
    print(f"Alert sent: {message}")
else:
    print(f"All clear — peak gust only {peak_gust} mph during pool hours.")
