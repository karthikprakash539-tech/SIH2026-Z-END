"""
Seed demo users for BlockSync.

Place at: backend/auth/seed_users.py
Run from inside backend/auth/:

    python seed_users.py

Creates 4 demo accounts covering every role, all with password "demo1234"
(fine for a hackathon demo -- never do this in a real deployment).
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "models"))

from models import engine, User
from sqlalchemy.orm import sessionmaker
from security import hash_password

Session = sessionmaker(bind=engine)
session = Session()

DEMO_USERS = [
    ("engineer_officer", "engineering_officer"),
    ("signal_officer", "signal_officer"),
    ("traction_officer", "traction_officer"),
    ("admin", "admin"),
]

for username, role in DEMO_USERS:
    existing = session.query(User).filter(User.username == username).first()
    if existing:
        print(f"[skip] {username} already exists")
        continue
    user = User(username=username, hashed_password=hash_password("demo1234"), role=role)
    session.add(user)
    print(f"[ok] created user '{username}' with role '{role}'")

session.commit()
print("\nDone. All demo accounts use password: demo1234")