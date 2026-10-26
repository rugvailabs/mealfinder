"""Grant a role to a phone number, creating the account if needed. Used to bootstrap admins.

uv run python -m scripts.grant_role +919876543210 admin
"""

import asyncio
import sys

import app.modules  # noqa: F401  load every model so foreign keys resolve
from app.core.auth import Role
from app.core.db import get_sessionmaker
from app.modules.identity import service
from app.modules.identity.schemas import OtpRequest


async def main(phone: str, role: Role) -> None:
    phone = OtpRequest(phone=phone).phone
    async with get_sessionmaker()() as db:
        user = await service.get_or_create_user(db, phone)
        await service.grant_role(db, user.id, role)
        await db.commit()
        print(f"{phone} now has roles: {[r.value for r in await service.roles_for(db, user.id)]}")


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[2] not in Role.__members__.values():
        sys.exit(f"usage: python -m scripts.grant_role <phone> <{'|'.join(Role)}>")
    asyncio.run(main(sys.argv[1], Role(sys.argv[2])))
