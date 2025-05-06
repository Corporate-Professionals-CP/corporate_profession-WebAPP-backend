from sqlmodel import Session, select
from app.models.follow import UserFollow
from app.models.user import User
from typing import List

def follow_user(db: Session, follower: User, followed: User) -> UserFollow:
    """Create a follow relationship between users"""
    # Check if not already following
    existing = db.exec(
        select(UserFollow).where(
            UserFollow.follower_id == follower.id,
            UserFollow.followed_id == followed.id
        )
    ).first()
    
    if existing:
        return existing
    
    follow_entry = UserFollow(follower_id=follower.id, followed_id=followed.id)
    db.add(follow_entry)
    db.commit()
    db.refresh(follow_entry)
    return follow_entry

def unfollow_user(db: Session, follower: User, followed: User) -> None:
    """Remove a follow relationship between users"""
    db.exec(
        select(UserFollow).where(
            UserFollow.follower_id == follower.id,
            UserFollow.followed_id == followed.id
        )
    ).delete()
    db.commit()

def get_following(db: Session, user: User) -> List[User]:
    """Get all users that a given user is following"""
    return db.exec(
        select(User).join(UserFollow, User.id == UserFollow.followed_id)
        .where(UserFollow.follower_id == user.id)
    ).all()

def get_followers(db: Session, user: User) -> List[User]:
    """Get all users following a given user"""
    return db.exec(
        select(User).join(UserFollow, User.id == UserFollow.follower_id)
        .where(UserFollow.followed_id == user.id)
    ).all()
