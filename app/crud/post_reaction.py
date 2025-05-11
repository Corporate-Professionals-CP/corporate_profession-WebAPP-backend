from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from app.models.post_reaction import PostReaction
from app.schemas.post_reaction import PostReactionCreate
from app.models.user import User


async def add_or_update_reaction(db: AsyncSession, user: User, reaction: PostReactionCreate) -> PostReaction:
    result = await db.execute(
        select(PostReaction).where(
            PostReaction.user_id == user.id,
            PostReaction.post_id == reaction.post_id
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        existing.type = reaction.type
        await db.commit()
        await db.refresh(existing)
        return existing

    new_reaction = PostReaction(
        user_id=user.id,
        post_id=reaction.post_id,
        type=reaction.type
    )
    db.add(new_reaction)
    await db.commit()
    await db.refresh(new_reaction)
    return new_reaction


async def get_reactions_for_post(db: AsyncSession, post_id: str) -> list[PostReaction]:
    result = await db.execute(
        select(PostReaction).where(PostReaction.post_id == post_id)
    )
    return result.scalars().all()


async def remove_reaction(db: AsyncSession, user_id: str, post_id: str) -> bool:
    result = await db.execute(
        select(PostReaction).where(
            PostReaction.user_id == user_id,
            PostReaction.post_id == post_id
        )
    )
    reaction = result.scalar_one_or_none()
    if reaction:
        await db.delete(reaction)
        await db.commit()
        return True
    return False
