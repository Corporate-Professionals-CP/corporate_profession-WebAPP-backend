import asyncio
from uuid import UUID
from app.db.database import AsyncSessionLocal
from app.models import User

async def make_admin(user_id: str):
    async with AsyncSessionLocal() as session:
        user = await session.get(User, user_id)
        if user:
            user.is_admin = True
            session.add(user)
            await session.commit()
            print(f"{user.email} is now admin.")
        else:
            print("User not found.")

if __name__ == "__main__":
    import sys
    user_id = sys.argv[1]
    asyncio.run(make_admin(user_id))

