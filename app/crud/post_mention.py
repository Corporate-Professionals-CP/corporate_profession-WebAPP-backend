import re
from typing import List, Optional, Dict, Any, Tuple
from sqlmodel import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.post_mention import PostMention
from app.models.user import User
from app.models.post import Post
from app.schemas.post_mention import PostMentionCreate, MentionSuggestion
from app.crud.connection import get_my_connections


def parse_mentions_from_content(content: str) -> List[Dict[str, Any]]:
    """Parse @mentions from post content"""
    # Regex pattern to match @username or @"Full Name"
    mention_pattern = r'@(?:"([^"]+)"|([a-zA-Z0-9_.-]+))'
    mentions = []
    
    for match in re.finditer(mention_pattern, content):
        mention_text = match.group(1) or match.group(2)  # Quoted name or username
        start_pos = match.start()
        end_pos = match.end()
        
        mentions.append({
            "mention_text": mention_text,
            "position_start": start_pos,
            "position_end": end_pos,
            "full_match": match.group(0)
        })
    
    return mentions


async def resolve_mentions_to_users(db: AsyncSession, mentions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Resolve mention text to actual users"""
    resolved_mentions = []
    
    for mention in mentions:
        mention_text = mention["mention_text"]
        
        # Try to find user by username first, then by full name
        user = None
        
        # Check if it looks like a username (no spaces, alphanumeric + underscore/dash)
        if re.match(r'^[a-zA-Z0-9_.-]+$', mention_text):
            # Search by username (assuming we add username field to User model)
            # For now, search by email or other unique identifier
            user = (await db.exec(
                select(User).where(
                    or_(
                        User.email.ilike(f"%{mention_text}%"),
                        User.full_name.ilike(f"%{mention_text}%")
                    )
                )
            )).first()
        else:
            # Search by full name
            user = (await db.exec(
                select(User).where(User.full_name.ilike(f"%{mention_text}%"))
            )).first()
        
        if user:
            resolved_mentions.append({
                **mention,
                "user_id": user.id,
                "user": user
            })
    
    return resolved_mentions


async def create_post_mentions(
    db: AsyncSession, 
    post_id: str, 
    content: str, 
    mentioned_by_user_id: str
) -> List[PostMention]:
    """Create post mentions from content"""
    # Parse mentions from content
    mentions = parse_mentions_from_content(content)
    
    if not mentions:
        return []
    
    # Resolve mentions to users
    resolved_mentions = await resolve_mentions_to_users(db, mentions)
    
    # Create PostMention records
    post_mentions = []
    for mention in resolved_mentions:
        post_mention = PostMention(
            post_id=post_id,
            mentioned_user_id=mention["user_id"],
            mentioned_by_user_id=mentioned_by_user_id,
            mention_text=mention["mention_text"],
            position_start=mention["position_start"],
            position_end=mention["position_end"]
        )
        db.add(post_mention)
        post_mentions.append(post_mention)
    
    await db.commit()
    return post_mentions


async def get_post_mentions(db: AsyncSession, post_id: str) -> List[PostMention]:
    """Get all mentions for a post"""
    return (await db.exec(
        select(PostMention).where(PostMention.post_id == post_id)
    )).all()


async def get_user_mentions(
    db: AsyncSession, 
    user_id: str, 
    skip: int = 0, 
    limit: int = 20
) -> List[PostMention]:
    """Get mentions where user was mentioned"""
    return (await db.exec(
        select(PostMention)
        .where(PostMention.mentioned_user_id == user_id)
        .order_by(PostMention.created_at.desc())
        .offset(skip)
        .limit(limit)
    )).all()


async def search_users_for_mention(
    db: AsyncSession, 
    query: str, 
    current_user_id: str, 
    limit: int = 10
) -> List[MentionSuggestion]:
    """Search users for @mention autocomplete"""
    if len(query) < 2:
        return []
    
    # Get user's connections for prioritization
    connections = await get_my_connections(db, current_user_id)
    connected_user_ids = [conn.sender_id if conn.receiver_id == current_user_id else conn.receiver_id 
                         for conn in connections]
    
    # Search users by name or email
    users = (await db.exec(
        select(User)
        .where(
            and_(
                User.id != current_user_id,  # Exclude current user
                User.is_active == True,
                or_(
                    User.full_name.ilike(f"%{query}%"),
                    User.email.ilike(f"%{query}%")
                )
            )
        )
        .limit(limit * 2)  # Get more to prioritize connections
    )).all()
    
    # Convert to mention suggestions and prioritize connections
    suggestions = []
    connected_suggestions = []
    
    for user in users:
        suggestion = MentionSuggestion(
            id=user.id,
            full_name=user.full_name,
            username=user.email.split('@')[0] if user.email else None,  # Temporary username
            profile_image_url=f"{user.profile_image_url}?v={int(user.profile_image_uploaded_at.timestamp())}" if user.profile_image_url and user.profile_image_uploaded_at else user.profile_image_url,
            job_title=user.job_title,
            company=user.company,
            is_connected=user.id in connected_user_ids
        )
        
        if suggestion.is_connected:
            connected_suggestions.append(suggestion)
        else:
            suggestions.append(suggestion)
    
    # Return connected users first, then others
    return (connected_suggestions + suggestions)[:limit]


async def delete_post_mentions(db: AsyncSession, post_id: str) -> bool:
    """Delete all mentions for a post"""
    mentions = (await db.exec(
        select(PostMention).where(PostMention.post_id == post_id)
    )).all()
    
    for mention in mentions:
        await db.delete(mention)
    
    await db.commit()
    return True


async def update_post_mentions(
    db: AsyncSession, 
    post_id: str, 
    new_content: str, 
    mentioned_by_user_id: str
) -> List[PostMention]:
    """Update mentions when post content is edited"""
    # Delete existing mentions
    await delete_post_mentions(db, post_id)
    
    # Create new mentions
    return await create_post_mentions(db, post_id, new_content, mentioned_by_user_id)


async def get_mention_notifications(
    db: AsyncSession, 
    user_id: str, 
    unread_only: bool = True,
    skip: int = 0,
    limit: int = 20
) -> List[Dict[str, Any]]:
    """Get mention notifications for a user"""
    # This would integrate with the notification system
    # For now, return recent mentions
    mentions = await get_user_mentions(db, user_id, skip, limit)
    
    notifications = []
    for mention in mentions:
        # Get the post and mentioning user
        post = (await db.exec(select(Post).where(Post.id == mention.post_id))).first()
        mentioning_user = (await db.exec(select(User).where(User.id == mention.mentioned_by_user_id))).first()
        
        if post and mentioning_user:
            notifications.append({
                "id": mention.id,
                "type": "mention",
                "post_id": post.id,
                "post_title": post.title or "Untitled Post",
                "post_content_preview": post.content[:100] + "..." if len(post.content) > 100 else post.content,
                "mentioning_user": {
                    "id": mentioning_user.id,
                    "full_name": mentioning_user.full_name,
                    "profile_image_url": f"{mentioning_user.profile_image_url}?v={int(mentioning_user.profile_image_uploaded_at.timestamp())}" if mentioning_user.profile_image_url and mentioning_user.profile_image_uploaded_at else mentioning_user.profile_image_url
                },
                "mentioned_at": mention.created_at,
                "mention_text": mention.mention_text
            })
    
    return notifications


def format_content_with_mentions(content: str, mentions: List[PostMention]) -> str:
    """Format content with clickable mention links (for frontend)"""
    if not mentions:
        return content
    
    # Sort mentions by position (reverse order to maintain positions)
    sorted_mentions = sorted(mentions, key=lambda x: x.position_start, reverse=True)
    
    formatted_content = content
    for mention in sorted_mentions:
        # Replace mention text with formatted link
        mention_link = f'<a href="/profile/{mention.mentioned_user_id}" class="mention">@{mention.mention_text}</a>'
        formatted_content = (
            formatted_content[:mention.position_start] + 
            mention_link + 
            formatted_content[mention.position_end:]
        )
    
    return formatted_content