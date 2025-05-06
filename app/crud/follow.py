from sqlmodel import Session, select, and_
from app.models.follow import UserFollow
from app.models.user import User
from typing import List, Optional

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

def check_follows_back(db: Session, target_id: str, current_user_id: str) -> bool:
    """Check if target user follows current user"""
    return db.exec(
        select(UserFollow).where(
            UserFollow.follower_id == target_id,
            UserFollow.followed_id == current_user_id
        )
    ).first() is not None

def get_mutual_followers_count(db: Session, user_a_id: str, user_b_id: str) -> int:
    """Get count of mutual followers users"""
    # Get users followed by both
    user_a_followers = select(UserFollow.follower_id).where(UserFollow.followed_id == user_a_id)
    user_b_followers = select(UserFollow.follower_id).where(UserFollow.followed_id == user_b_id)
    
    mutual_query = select(func.count()).select_from(
        user_a_followers.intersect(user_b_followers).subquery()
    )
    return db.execute(mutual_query).scalar()

def get_sample_mutuals(db: Session, user_a_id: str, user_b_id: str, limit: int = 3) -> List[str]:
    """Get sample mutual followers """
    user_a_followers = select(UserFollow.follower_id).where(UserFollow.followed_id == user_a_id)
    user_b_followers = select(UserFollow.follower_id).where(UserFollow.followed_id == user_b_id)
    
    mutual_ids = user_a_followers.intersect(user_b_followers).subquery()
    
    result = db.exec(
        select(User.username)
        .join(mutual_ids, User.id == mutual_ids.c.follower_id)
        .limit(limit)
    )
    return [row[0] for row in result.all()]


