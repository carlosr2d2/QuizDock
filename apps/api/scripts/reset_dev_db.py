"""Wipe all application data and seed a high-credit demo user.

Usage (Docker):
    docker compose exec api python scripts/reset_dev_db.py --yes

Usage (local, from apps/api):
    python scripts/reset_dev_db.py --yes
"""

from __future__ import annotations

import argparse
import asyncio
import shutil
import sys
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

# Ensure `app` is importable when run as a file from /app or apps/api.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app.models  # noqa: F401
from app.core.config import get_settings
from app.core.security import hash_password
from app.models import CreditTransaction, Membership, MembershipRole, Organization, PlanTier, User

settings = get_settings()
engine = create_async_engine(settings.database_url, echo=False, pool_pre_ping=True)
Session = async_sessionmaker(engine, expire_on_commit=False)

TABLES = [
    "error_reports",
    "credit_transactions",
    "flashcards",
    "exam_group_assignments",
    "group_members",
    "groups",
    "exam_assignments",
    "exam_attempts",
    "questions",
    "exams",
    "generation_jobs",
    "document_chunks",
    "documents",
    "invitations",
    "password_reset_tokens",
    "memberships",
    "users",
    "organizations",
]


async def wipe(session) -> None:
    quoted = ", ".join(TABLES)
    await session.execute(text(f"TRUNCATE TABLE {quoted} RESTART IDENTITY CASCADE"))
    await session.commit()


def wipe_storage() -> None:
    storage = Path(settings.storage_dir)
    if not storage.exists():
        return
    for child in storage.iterdir():
        if child.name == ".gitkeep":
            continue
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()


async def seed(session, email: str, password: str, full_name: str, credits: int) -> User:
    org = Organization(
        name="Demo workspace",
        slug="demo",
        plan=PlanTier.INDIVIDUAL,
        is_personal=True,
        credit_balance=credits,
        billing_country="CO",
    )
    session.add(org)
    await session.flush()

    user = User(
        email=email.lower(),
        hashed_password=hash_password(password),
        full_name=full_name,
        locale="es",
        personal_organization_id=org.id,
    )
    session.add(user)
    await session.flush()

    session.add(
        Membership(
            user_id=user.id,
            organization_id=org.id,
            role=MembershipRole.OWNER,
        )
    )
    session.add(
        CreditTransaction(
            organization_id=org.id,
            user_id=user.id,
            amount=credits,
            reason="dev_seed",
            balance_after=credits,
        )
    )

    team = Organization(
        name="Demo empresa",
        slug="demo-empresa",
        plan=PlanTier.TEAM,
        is_personal=False,
        credit_balance=credits,
        billing_country="CO",
    )
    session.add(team)
    await session.flush()
    session.add(
        Membership(
            user_id=user.id,
            organization_id=team.id,
            role=MembershipRole.OWNER,
        )
    )
    session.add(
        CreditTransaction(
            organization_id=team.id,
            user_id=user.id,
            amount=credits,
            reason="dev_seed_team",
            balance_after=credits,
        )
    )
    await session.commit()
    await session.refresh(user)
    return user


async def main() -> None:
    parser = argparse.ArgumentParser(description="Reset QuizDock DB and seed a demo user.")
    parser.add_argument("--yes", action="store_true", help="Do not ask for confirmation.")
    parser.add_argument("--email", default="demo@example.com")
    parser.add_argument("--password", default="demo12345")
    parser.add_argument("--name", default="Demo Tester")
    parser.add_argument("--credits", type=int, default=10_000)
    args = parser.parse_args()

    if settings.environment == "production":
        raise SystemExit("Refusing to reset a production database.")

    if not args.yes:
        confirm = input("This will DELETE all QuizDock data. Continue? [y/N] ").strip().lower()
        if confirm not in {"y", "yes"}:
            raise SystemExit("Aborted.")

    async with Session() as session:
        await wipe(session)
        wipe_storage()
        user = await seed(session, args.email, args.password, args.name, args.credits)
    await engine.dispose()

    print("Database reset.")
    print(f"  email:    {user.email}")
    print(f"  password: {args.password}")
    print(f"  credits:  {args.credits}")
    print("  login:    http://localhost:3000/login")


if __name__ == "__main__":
    asyncio.run(main())
