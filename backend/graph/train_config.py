"""
Shared train selection config.

Place at: backend/graph/train_config.py

Single source of truth for which real trains build the network. Both
load_data.py (builds Section rows) and train_schedule.py (builds
animated train movement) import this list, so the sections that exist
in the DB always match the trains whose movement we can animate --
no drift between the two.
"""

TARGET_TRAIN_NOS = [
    "128", "12346", "12423", "12424", "12503", "12504",
    "12507", "12508", "12509", "12510", "15629", "15630",
]
