import asyncio
from uuid import UUID
from app.db.database import AsyncSessionLocal
from app.models import User

async def make_moderator(user_id: str):
    """Set a user as a moderator"""
    async with AsyncSessionLocal() as session:
        user = await session.get(User, user_id)
        if user:
            user.is_moderator = True
            session.add(user)
            await session.commit()
            print(f"{user.email} is now a moderator.")
        else:
            print("User not found.")

async def remove_moderator(user_id: str):
    """Remove moderator status from a user"""
    async with AsyncSessionLocal() as session:
        user = await session.get(User, user_id)
        if user:
            user.is_moderator = False
            session.add(user)
            await session.commit()
            print(f"Moderator status removed from {user.email}.")
        else:
            print("User not found.")

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("Usage: python -m app.scripts.create_moderator [add|remove] [user_id]")
        sys.exit(1)
    
    action = sys.argv[1].lower()
    user_id = sys.argv[2]
    
    if action == "add":
        asyncio.run(make_moderator(user_id))
    elif action == "remove":
        asyncio.run(remove_moderator(user_id))
    else:
        print("Invalid action. Use 'add' or 'remove'.")