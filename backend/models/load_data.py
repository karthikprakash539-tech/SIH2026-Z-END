"""
BlockSync data ingestion script -- MULTI-TRAIN NETWORK version.

Place at: backend/models/load_data.py (replaces the single-corridor version)
Run from inside backend/models/ (same folder as models.py and blocksync.db):

    python load_data.py

CHANGE FROM PREVIOUS VERSION:
The old script built sections from ONE train's route, producing a single
straight line (S01 -> S02 -> ... -> S20) with no branches or junctions.

This version reads MULTIPLE trains from train_timetable.csv and merges
their routes into a shared network: whenever two different trains both
pass through the same pair of consecutive stations, they reuse the SAME
Section row instead of creating a duplicate. A station that ends up
connected to 3+ sections is therefore a real junction -- it emerges
naturally from the data, we don't have to hand-model it.

traffic_density on a Section is now meaningful: it's the number of
distinct trains that share that section, so heavily-used junctions
score higher automatically (this feeds straight into the optimizer's
existing priority formula, no change needed there).
"""

import json
import os
import csv
import sys
from collections import defaultdict
from models import Base, engine, Section, Defect
from sqlalchemy.orm import sessionmaker

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "graph"))
from train_config import TARGET_TRAIN_NOS

Session = sessionmaker(bind=engine)
session = Session()

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------
TIMETABLE_PATH = "../../data/raw/train_timetable.csv"
MOCK_DATA_DIR = "../../data/mock"

# TARGET_TRAIN_NOS now lives in backend/graph/train_config.py -- shared
# with train_schedule.py so the sections we build here always match the
# trains we can animate moving across them.

FALLBACK_ROUTES = {
    "128": [
        {"seq": 1, "station": "New Delhi", "distance": 0},
        {"seq": 2, "station": "Ghaziabad", "distance": 25},
        {"seq": 3, "station": "Kanpur Central", "distance": 440},
        {"seq": 4, "station": "Allahabad Jn", "distance": 640},
    ]
}


def load_all_routes(csv_path, train_nos):
    """Read the timetable once, return {train_no: [stop, stop, ...]} for
    every requested train, each list sorted by SEQ."""
    routes = defaultdict(list)

    if not os.path.exists(csv_path):
        print(f"[warn] {csv_path} not found. Using fallback routes only.")
        return {tn: stops for tn, stops in FALLBACK_ROUTES.items() if tn in train_nos}

    with open(csv_path, newline="", encoding="utf-8", errors="ignore") as f:
        reader = csv.DictReader(f)
        for row in reader:
            tn = row.get("Train No", "").strip()
            if tn not in train_nos:
                continue
            try:
                routes[tn].append({
                    "seq": int(row["SEQ"]),
                    "station": row["Station Name"].strip(),
                    "distance": float(row["Distance"]),
                })
            except (ValueError, KeyError):
                continue

    for tn in routes:
        routes[tn].sort(key=lambda s: s["seq"])

    missing = [tn for tn in train_nos if tn not in routes or not routes[tn]]
    for tn in missing:
        if tn in FALLBACK_ROUTES:
            print(f"[warn] no rows found for Train No {tn}, using fallback route.")
            routes[tn] = FALLBACK_ROUTES[tn]
        else:
            print(f"[warn] no rows found for Train No {tn} and no fallback -- skipping.")

    return dict(routes)


def merge_routes_into_sections(routes):
    """Walk every train's consecutive stops and merge them into a shared
    set of Section records. Two trains sharing the same station pair
    (in either direction) reuse the same Section and its traffic_density
    (train count) increases. Returns the list of created/updated
    Section objects."""

    # key: frozenset({station_a, station_b}) -> accumulated info
    pair_info = {}   # key -> {"from": a, "to": b, "distance": km, "trains": set()}
    pair_order = []  # preserves first-seen order for stable section_id numbering

    for train_no, stops in routes.items():
        for i in range(len(stops) - 1):
            a, b = stops[i], stops[i + 1]
            key = frozenset((a["station"], b["station"]))
            dist = round(abs(b["distance"] - a["distance"]), 1) or 1.0

            if key not in pair_info:
                pair_info[key] = {
                    "from": a["station"],
                    "to": b["station"],
                    "distance": dist,
                    "trains": set(),
                }
                pair_order.append(key)
            pair_info[key]["trains"].add(train_no)

    sections = []
    for i, key in enumerate(pair_order):
        info = pair_info[key]
        section_id = f"S{i+1:02d}"
        train_count = len(info["trains"])

        existing = session.query(Section).filter_by(section_id=section_id).first()
        if existing:
            existing.from_station = info["from"]
            existing.to_station = info["to"]
            existing.distance_km = info["distance"]
            existing.traffic_density = float(train_count)
            sections.append(existing)
            continue

        sec = Section(
            section_id=section_id,
            from_station=info["from"],
            to_station=info["to"],
            distance_km=info["distance"],
            traffic_density=float(train_count),
        )
        session.add(sec)
        sections.append(sec)

    session.commit()

    # report junctions (stations touched by 3+ sections) so it's visible
    # immediately in the console that this actually built a network
    degree = defaultdict(int)
    for s in sections:
        degree[s.from_station] += 1
        degree[s.to_station] += 1
    junctions = sorted([st for st, d in degree.items() if d >= 3], key=lambda st: -degree[st])

    print(f"[ok] created/updated {len(sections)} sections from {len(routes)} train routes")
    for s in sections:
        print(f"      {s.section_id}: {s.from_station} -> {s.to_station} "
              f"({s.distance_km} km, traffic_density={s.traffic_density})")
    print(f"[ok] {len(junctions)} junction stations detected (3+ connecting sections):")
    for st in junctions:
        print(f"      {st} -- {degree[st]} connections")

    return sections


def load_defects(mock_dir, sections):
    """Load the three mock defect JSON files and link each defect to a
    section -- matched by station name where possible, otherwise
    round-robin assigned so every defect still has a valid section_id."""
    files = ["tms_defects.json", "smms_defects.json", "tdms_defects.json"]
    total = 0
    for fname in files:
        path = os.path.join(mock_dir, fname)
        if not os.path.exists(path):
            print(f"[warn] {path} not found, skipping.")
            continue
        with open(path, encoding="utf-8") as f:
            records = json.load(f)

        for i, rec in enumerate(records):
            match = next(
                (s for s in sections if rec.get("section_id") in (s.from_station, s.to_station)),
                sections[i % len(sections)]
            )
            defect = Defect(
                department=rec.get("department"),
                section_id=match.id,
                defect_type=rec.get("defect_type"),
                severity={"Low": 1, "Medium": 2, "High": 4, "Critical": 5}.get(rec.get("severity"), 2),
                overdue_days=rec.get("overdue_days", 0),
                status=rec.get("status", "Open"),
            )
            session.add(defect)
            total += 1
        session.commit()
        print(f"[ok] loaded {len(records)} defects from {fname}")

    print(f"[ok] total defects loaded: {total}")


def main():
    Base.metadata.create_all(engine)  # safe no-op if tables already exist

    print(f"[info] building network from {len(TARGET_TRAIN_NOS)} train routes: {TARGET_TRAIN_NOS}")
    routes = load_all_routes(TIMETABLE_PATH, TARGET_TRAIN_NOS)
    if not routes:
        print("[error] no routes could be loaded -- check TIMETABLE_PATH / TARGET_TRAIN_NOS.")
        return

    sections = merge_routes_into_sections(routes)

    print("[info] loading defect data")
    load_defects(MOCK_DATA_DIR, sections)

    print("\nDone. Query the DB to confirm:")
    print('  python -c "from models import Session, Section, Defect; from sqlalchemy.orm import sessionmaker; from models import engine; s=sessionmaker(bind=engine)(); print(s.query(Section).count(), \'sections\'); print(s.query(Defect).count(), \'defects\')"')


if __name__ == "__main__":
    main()
