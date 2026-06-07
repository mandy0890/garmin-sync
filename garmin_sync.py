"""
Garmin Connect Daily Sync v3 – with HRV debug output
"""
import json
import os
import sys
from datetime import date, timedelta


def safe_get(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except Exception as e:
        print(f"  Warning: {fn.__name__} failed: {e}")
        return None


def main():
    try:
        from garminconnect import Garmin
    except ImportError:
        print("ERROR: pip install garminconnect")
        sys.exit(1)

    email = os.environ.get("GARMIN_EMAIL")
    password = os.environ.get("GARMIN_PASSWORD")
    if not email or not password:
        print("ERROR: GARMIN_EMAIL or GARMIN_PASSWORD not set")
        sys.exit(1)

    print(f"Logging in as {email}...")
    try:
        client = Garmin(email, password)
        client.login()
        print("Login OK.")
    except Exception as e:
        print(f"ERROR: Login failed: {e}")
        sys.exit(1)

    today = date.today().isoformat()
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    print(f"Fetching data for {today}...")

    # ── HRV – print raw structure for debugging ──
    hrv_raw = safe_get(client.get_hrv_data, today) or safe_get(client.get_hrv_data, yesterday)
    print(f"\n=== RAW HRV DATA ===\n{json.dumps(hrv_raw, indent=2, default=str)}\n===================\n")

    hrv = None
    if hrv_raw:
        try:
            summary = hrv_raw.get("hrvSummary", hrv_raw)
            # Try all known key variants
            nightly = (summary.get("lastNight") or
                       summary.get("lastNightAvg") or
                       summary.get("lastNight5MinHigh") or
                       summary.get("nightlyAvg") or
                       summary.get("value"))
            hrv = {
                "value": nightly,
                "status": summary.get("status", ""),
                "weekly_avg": summary.get("weeklyAvg"),
            }
        except Exception as e:
            print(f"  HRV parse error: {e}")

    # Sleep
    sleep_raw = safe_get(client.get_sleep_data, today) or safe_get(client.get_sleep_data, yesterday)
    sleep = None
    if sleep_raw:
        try:
            dto = sleep_raw.get("dailySleepDTO", sleep_raw)
            scores = dto.get("sleepScores", {})
            score = scores.get("overall", {}).get("value") if isinstance(scores, dict) else None
            score = score or dto.get("sleepScore")
            secs = dto.get("sleepTimeSeconds") or dto.get("totalSleepSeconds", 0)
            sleep = {"score": score, "duration_h": round(secs / 3600, 1) if secs else None}
        except Exception as e:
            print(f"  Sleep parse error: {e}")

    # Body Battery – three approaches
    body_battery = None
    bb_raw = safe_get(client.get_body_battery, today, today)
    if bb_raw and isinstance(bb_raw, list) and bb_raw:
        try:
            readings = bb_raw[0].get("bodyBatteryValuesArray", [])
            if readings:
                body_battery = readings[-1][1] if readings[-1] else None
        except: pass

    if body_battery is None:
        bb_raw2 = safe_get(client.get_body_battery, [today])
        if bb_raw2 and isinstance(bb_raw2, list) and bb_raw2:
            try:
                readings = bb_raw2[0].get("bodyBatteryValuesArray", [])
                if readings:
                    body_battery = readings[-1][1] if readings[-1] else None
            except: pass

    if body_battery is None:
        bb_raw3 = safe_get(client.get_stats, today)
        if bb_raw3:
            try:
                body_battery = (bb_raw3.get("bodyBatteryChargedValue") or
                                bb_raw3.get("bodyBatteryHighestValue") or
                                bb_raw3.get("bodyBatteryMostRecentValue"))
            except: pass

    # Training Readiness
    readiness_raw = safe_get(client.get_training_readiness, today)
    readiness = None
    if readiness_raw:
        try:
            item = readiness_raw[0] if isinstance(readiness_raw, list) else readiness_raw
            readiness = {
                "score": item.get("score") or item.get("trainingReadinessScore"),
                "level": item.get("level") or item.get("trainingReadinessLevel", ""),
            }
        except Exception as e:
            print(f"  Readiness parse error: {e}")

    output = {
        "date": today,
        "hrv": hrv,
        "sleep": sleep,
        "body_battery": body_battery,
        "readiness": readiness,
        "synced_at": today,
    }

    with open("garmin-data.json", "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\nSaved garmin-data.json:")
    print(json.dumps(output, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
