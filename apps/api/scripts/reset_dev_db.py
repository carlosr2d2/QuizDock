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
    "audit_events",
    "ai_decision_events",
    "payment_orders",
    "error_reports",
    "credit_transactions",
    "flashcards",
    "exam_group_assignments",
    "group_members",
    "groups",
    "exam_assignments",
    "appeal_action_logs",
    "appeal_resolutions",
    "appeal_evidence",
    "appeal_cases",
    "answer_references",
    "question_evidence",
    "document_chat_messages",
    "document_conversations",
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

# Personal workspaces only — invite these into Demo empresa.
EXTRA_SEED_USERS = [
    ("user01@example.com", "Ana Gomez"),
    ("user02@example.com", "Carlos Ruiz"),
    ("user03@example.com", "Laura Pérez"),
    ("user04@example.com", "Diego Torres"),
    ("user05@example.com", "Sofía Herrera"),
    ("user06@example.com", "Andrés Castro"),
    ("user07@example.com", "Valentina López"),
    ("user08@example.com", "Julián Morales"),
    ("user09@example.com", "Camila Vargas"),
    ("user10@example.com", "Mateo Rojas"),
    ("user11@example.com", "Isabella Díaz"),
    ("user12@example.com", "Santiago Gil"),
    ("user13@example.com", "Mariana Ortiz"),
    ("user14@example.com", "Nicolás Peña"),
    ("user15@example.com", "Daniela Suárez"),
    ("user16@example.com", "Felipe Ramírez"),
    ("user17@example.com", "Paula Méndez"),
    ("user18@example.com", "Sebastián Cruz"),
    ("user19@example.com", "Lucía Navarro"),
    ("user20@example.com", "Tomás Aguilar"),
    ("user21@example.com", "Elena Cárdenas"),
    ("user22@example.com", "Gabriel Pinto"),
    ("user23@example.com", "Sara Molina"),
    ("user24@example.com", "Emilio Ríos"),
    ("user25@example.com", "Natalia Vega"),
    ("user26@example.com", "Hugo Salazar"),
    ("user27@example.com", "Clara Pardo"),
    ("user28@example.com", "Iván Castaño"),
    ("user29@example.com", "Jimena León"),
    ("user30@example.com", "Pablo Duarte"),
    ("user31@example.com", "Renata Silva"),
    ("user32@example.com", "Óscar Beltrán"),
    ("user33@example.com", "Alicia Romero"),
    ("user34@example.com", "Bruno Espinosa"),
    ("user35@example.com", "Carla Fuentes"),
    ("user36@example.com", "David Quintero"),
    ("user37@example.com", "Emma Delgado"),
    ("user38@example.com", "Fernando Mora"),
    ("user39@example.com", "Gabriela Nieto"),
    ("user40@example.com", "Héctor Palacios"),
    ("user41@example.com", "Inés Cabrera"),
    ("user42@example.com", "Jorge Pineda"),
    ("user43@example.com", "Karina Soto"),
    ("user44@example.com", "Luis Arango"),
    ("user45@example.com", "Mónica Bustos"),
    ("user46@example.com", "Noel Cifuentes"),
    ("user47@example.com", "Olga Franco"),
    ("user48@example.com", "Pedro Ibarra"),
    ("user49@example.com", "Rocío Sandoval"),
    ("user50@example.com", "Simón Valdés"),
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

    extra_hash = hash_password(password)
    bonus = settings.signup_bonus_credits
    for index, (extra_email, extra_name) in enumerate(EXTRA_SEED_USERS, start=1):
        personal = Organization(
            name=f"{extra_name} workspace",
            slug=f"user-{index:02d}",
            plan=PlanTier.FREE,
            is_personal=True,
            credit_balance=bonus,
            billing_country="CO",
        )
        session.add(personal)
        await session.flush()
        extra = User(
            email=extra_email,
            hashed_password=extra_hash,
            full_name=extra_name,
            locale="es",
            personal_organization_id=personal.id,
        )
        session.add(extra)
        await session.flush()
        session.add(
            Membership(
                user_id=extra.id,
                organization_id=personal.id,
                role=MembershipRole.OWNER,
            )
        )
        session.add(
            CreditTransaction(
                organization_id=personal.id,
                user_id=extra.id,
                amount=bonus,
                reason="dev_seed",
                balance_after=bonus,
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
    print(f"  owner:    {user.email}")
    print(f"  password: {args.password}")
    print(f"  credits:  {args.credits}")
    print(f"  extras:   {len(EXTRA_SEED_USERS)} users (personal workspaces only, same password)")
    print("  login:    http://localhost:3000/login")
    for extra_email, extra_name in EXTRA_SEED_USERS:
        print(f"  {extra_email}  {extra_name}")


if __name__ == "__main__":
    asyncio.run(main())
