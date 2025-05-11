from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from app.db.database import get_db
from app.schemas.post_reaction import PostReactionCreate, PostReactionRead
from app.crud.post_reaction import (
    add_or_update_reaction,
    remove_reaction,
    get_reactions_for_post,
)
from app.core.security import get_current_user
from app.models.user import User

router = APIRouter(prefix="/reactions", tags=["Post Reactions"])


@router.post("/", response_model=PostReactionRead, status_code=status.HTTP_200_OK)
async def react_to_post(
    reaction_in: PostReactionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return await add_or_update_reaction(db=db, user=current_user, reaction=reaction_in)


@router.get("/post/{post_id}", response_model=List[PostReactionRead])
async def fetch_reactions(
    post_id: str,
    db: AsyncSession = Depends(get_db)
):
    return await get_reactions_for_post(db=db, post_id=post_id)

@router.delete("/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_reaction(
    post_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    success = await remove_reaction(db=db, user_id=current_user.id, post_id=post_id)
    if not success:
        raise HTTPException(status_code=404, detail="Reaction not found")

