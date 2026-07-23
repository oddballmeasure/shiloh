from __future__ import annotations

import argparse
from typing import Sequence

from pymongo import MongoClient

from shiloh.config import get_settings
from shiloh.schemas import UserRole
from shiloh.utils import utcnow


def _collection():
    settings = get_settings()
    client = MongoClient(settings.mongo_url)
    return client[settings.mongo_db_name].users


def _find_user(discord_id: str):
    return _collection().find_one({"discord_id": discord_id})


def grant_super_admin(discord_id: str) -> int:
    user = _find_user(discord_id)
    if user is None:
        print(
            f"User with Discord ID {discord_id} does not exist. They must log in first."
        )
        return 1
    _collection().update_one(
        {"_id": user["_id"]},
        {"$set": {"role": UserRole.super_admin.value, "updated_at": utcnow()}},
    )
    print(f"Granted super_admin to Discord ID {discord_id}.")
    return 0


def revoke_super_admin(discord_id: str) -> int:
    user = _find_user(discord_id)
    if user is None:
        print(f"User with Discord ID {discord_id} does not exist.")
        return 1
    _collection().update_one(
        {"_id": user["_id"]},
        {"$set": {"role": UserRole.learner.value, "updated_at": utcnow()}},
    )
    print(f"Revoked super_admin from Discord ID {discord_id}.")
    return 0


def show_user(discord_id: str) -> int:
    user = _find_user(discord_id)
    if user is None:
        print(f"User with Discord ID {discord_id} does not exist.")
        return 1
    print(
        f"id={user['_id']} discord_id={user.get('discord_id')} "
        f"email={user.get('email')} role={user.get('role')} status={user.get('status')}"
    )
    return 0


def list_users(role: str | None) -> int:
    filters = {"role": role} if role else {}
    for user in _collection().find(filters).sort("created_at", -1):
        print(
            f"discord_id={user.get('discord_id')} "
            f"email={user.get('email')} role={user.get('role')} status={user.get('status')}"
        )
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="shiloh-admin")
    subparsers = parser.add_subparsers(dest="command", required=True)

    grant_parser = subparsers.add_parser("grant-super-admin")
    grant_parser.add_argument("--discord-id", required=True)

    revoke_parser = subparsers.add_parser("revoke-super-admin")
    revoke_parser.add_argument("--discord-id", required=True)

    show_parser = subparsers.add_parser("show-user")
    show_parser.add_argument("--discord-id", required=True)

    list_parser = subparsers.add_parser("list-users")
    list_parser.add_argument(
        "--role", choices=[role.value for role in UserRole], default=None
    )

    args = parser.parse_args(argv)
    if args.command == "grant-super-admin":
        return grant_super_admin(args.discord_id)
    if args.command == "revoke-super-admin":
        return revoke_super_admin(args.discord_id)
    if args.command == "show-user":
        return show_user(args.discord_id)
    if args.command == "list-users":
        return list_users(args.role)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
