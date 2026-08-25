"""
BlockSync Train Schedule Builder (for network animation).

Place at: backend/graph/train_schedule.py

Reads real per-stop arrival/departure times from train_timetable.csv and
turns each train into an ordered list of stops with ABSOLUTE seconds
(handling midnight rollover -- a train departing 23:52 and arriving
0:34 at the next stop is a 42-minute hop, not a 23-hour one going
backward). Each hop between consecutive stops is matched to an existing
Section (built by load_data.py from the same TARGET_TRAIN_NOS list) so
the frontend can place a moving marker on the correct graph edge.

Time format in the source CSV is H:MM:SS (variable-width hour, e.g.
"0:00:00", "23:52:00") -- parsed manually rather than with strptime's
%H to avoid the single/double-digit hour mismatch.
"""

import os
import csv
from collections import defaultdict
from train_config import TARGET_TRAIN_NOS


def _parse_hms(value):
    """'H:MM:SS' -> seconds since midnight. Returns None if unparseable
    (blank/malformed cells are skipped rather than crashing ingestion)."""
    if not value:
        return None
    parts = value.strip().split(":")
    if len(parts) != 3:
        return None
    try:
        h, m, s = (int(p) for p in parts)
        return h * 3600 + m * 60 + s
    except ValueError:
        return None


def _read_raw_stops(csv_path, train_nos):
    """Returns {train_no: [ {seq, station, arrival_raw, departure_raw,
    distance}, ... ]} sorted by seq, straight from the CSV with no
    rollover resolution yet."""
    trains = defaultdict(list)
    if not os.path.exists(csv_path):
        return {}

    with open(csv_path, newline="", encoding="utf-8", errors="ignore") as f:
        reader = csv.DictReader(f)
        for row in reader:
            tn = row.get("Train No", "").strip()
            if tn not in train_nos:
                continue
            arrival_raw = _parse_hms(row.get("Arrival time", ""))
            departure_raw = _parse_hms(row.get("Departure time", ""))
            if arrival_raw is None or departure_raw is None:
                continue
            try:
                seq = int(row["SEQ"])
                distance = float(row["Distance"])
            except (KeyError, ValueError, TypeError):
                continue
            trains[tn].append({
                "seq": seq,
                "station": row["Station Name"].strip(),
                "arrival_raw": arrival_raw,
                "departure_raw": departure_raw,
                "distance": distance,
            })

    for tn in trains:
        trains[tn].sort(key=lambda s: s["seq"])
    return dict(trains)


def _resolve_rollover(stops):
    """Turns per-stop clock times (seconds since midnight, resets every
    24h) into a monotonically increasing absolute-seconds timeline.
    The first stop's 'arrival' is a placeholder (it's the origin, there
    is no incoming leg) so we anchor on its departure instead."""
    resolved = []
    day_offset = 0
    prev_time = None

    for i, s in enumerate(stops):
        if i == 0:
            arrival_abs = s["departure_raw"]
            departure_abs = s["departure_raw"]
        else:
            arrival_candidate = s["arrival_raw"] + day_offset * 86400
            if prev_time is not None and arrival_candidate < prev_time:
                day_offset += 1
                arrival_candidate = s["arrival_raw"] + day_offset * 86400
            arrival_abs = arrival_candidate

            departure_candidate = s["departure_raw"] + day_offset * 86400
            if departure_candidate < arrival_abs:
                departure_candidate += 86400
            departure_abs = departure_candidate

        resolved.append({
            "seq": s["seq"],
            "station": s["station"],
            "arrival_sec": arrival_abs,
            "departure_sec": departure_abs,
            "distance_km": s["distance"],
        })
        prev_time = departure_abs

    return resolved


def build_train_schedules(csv_path, section_lookup, train_nos=None):
    """section_lookup: {frozenset({station_a, station_b}): {"section_id":
    str, "db_id": int}} -- built by the caller from the Section table.

    Returns:
        {
          "trains": [
            {
              "train_no": str,
              "stops": [{station, arrival_sec, departure_sec, distance_km}, ...],
              "hops": [{section_id, from, to, departure_sec, arrival_sec}, ...]
            }, ...
          ],
          "time_range": {"min_sec": int, "max_sec": int}
        }
    """
    train_nos = train_nos or TARGET_TRAIN_NOS
    raw = _read_raw_stops(csv_path, train_nos)

    trains_out = []
    min_sec, max_sec = None, None

    for tn, stops in raw.items():
        if len(stops) < 2:
            continue  # need at least 2 stops to have a movable hop
        resolved = _resolve_rollover(stops)

        hops = []
        for i in range(len(resolved) - 1):
            a, b = resolved[i], resolved[i + 1]
            key = frozenset((a["station"], b["station"]))
            match = section_lookup.get(key)
            if not match:
                continue  # station pair not in the built network -- skip this hop
            hops.append({
                "section_id": match["section_id"],
                "from": a["station"],
                "to": b["station"],
                "departure_sec": a["departure_sec"],
                "arrival_sec": b["arrival_sec"],
            })

        if not hops:
            continue

        train_min = resolved[0]["departure_sec"]
        train_max = resolved[-1]["arrival_sec"]
        min_sec = train_min if min_sec is None else min(min_sec, train_min)
        max_sec = train_max if max_sec is None else max(max_sec, train_max)

        trains_out.append({
            "train_no": tn,
            "stops": resolved,
            "hops": hops,
        })

    return {
        "trains": trains_out,
        "time_range": {"min_sec": min_sec or 0, "max_sec": max_sec or 0},
    }
