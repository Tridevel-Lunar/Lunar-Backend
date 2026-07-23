"""Seed Mission 01 Perfect-pass Blockly AST into arena_attempts."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime

from sqlalchemy import select

from app.arena.missions import get_mission_pack
from app.arena.missions.m01_pass_solution import M01_PASS_AST
from app.db.session import SessionLocal
from app.models.arena_attempt import ArenaAttempt
from app.models.user import User

MISSION_ID = "leo-orbit-one-lap"


def _resolve_user(session, email: str | None) -> User:
    if email:
        user = session.scalar(select(User).where(User.email == email))
        if user is None:
            raise SystemExit(f"No user found for email: {email}")
        return user

    user = session.scalar(select(User).order_by(User.created_at.asc()))
    if user is None:
        raise SystemExit("No users in database. Sign in once, then rerun this script.")
    return user


def seed_pass_attempt(email: str | None = None, *, overwrite: bool = True) -> None:
    pack = get_mission_pack(MISSION_ID)
    if pack is None:
        raise SystemExit(f"Unknown mission: {MISSION_ID}")

    mission_version = int(pack.get("version", 1))
    now = datetime.now(UTC)

    with SessionLocal() as session:
        user = _resolve_user(session, email)
        row = session.scalar(
            select(ArenaAttempt).where(
                ArenaAttempt.user_id == user.id,
                ArenaAttempt.mission_id == MISSION_ID,
            )
        )
        if row is None:
            row = ArenaAttempt(
                user_id=user.id,
                mission_id=MISSION_ID,
                ast=M01_PASS_AST,
                workspace=None,
                mission_version=mission_version,
                last_result=None,
                created_at=now,
                updated_at=now,
            )
            session.add(row)
            action = "created"
        elif overwrite:
            row.ast = M01_PASS_AST
            # Clear Blockly layout so the FE restores from AST (workspace wins over ast).
            row.workspace = None
            row.mission_version = mission_version
            row.updated_at = now
            action = "updated"
        else:
            print(f"Attempt already exists for {user.email}; use --overwrite to replace.")
            return

        session.commit()
        print(
            f"{action} Mission 01 pass AST for user {user.email} "
            f"(mission_version={mission_version})"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--email",
        help="Target user email (defaults to earliest registered user)",
    )
    parser.add_argument(
        "--no-overwrite",
        action="store_true",
        help="Skip if an attempt already exists for this user/mission",
    )
    args = parser.parse_args()
    seed_pass_attempt(args.email, overwrite=not args.no_overwrite)


if __name__ == "__main__":
    main()
