from typing import List, Optional
from sqlmodel import Session, select
from app.models.post import Post
from app.schemas.post import PostCreate, PostUpdate

def create_post(session: Session, post_data: PostCreate) -> Post:
    """
    Create a new post in the database.
    
    Args:
        session (Session): Database session.
        post_data (PostCreate): Data for creating a new post.
    
    Returns:
        Post: The newly created post object.
    """
    db_post = Post.from_orm(post_data)
    session.add(db_post)
    session.commit()
    session.refresh(db_post)
    return db_post

def get_post_by_id(session: Session, post_id: str) -> Optional[Post]:
    """
    Retrieve a post by its unique identifier.
    
    Args:
        session (Session): Database session.
        post_id (str): The unique identifier of the post.
    
    Returns:
        Optional[Post]: The post if found; otherwise, None.
    """
    statement = select(Post).where(Post.id == post_id)
    return session.exec(statement).first()

def update_post(session: Session, post_id: str, post_update: PostUpdate) -> Optional[Post]:
    """
    Update an existing post.
    
    Args:
        session (Session): Database session.
        post_id (str): The unique identifier of the post to update.
        post_update (PostUpdate): The update payload containing new data.
    
    Returns:
        Optional[Post]: The updated post if found; otherwise, None.
    """
    db_post = get_post_by_id(session, post_id)
    if not db_post:
        return None

    update_data = post_update.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_post, key, value)

    session.add(db_post)
    session.commit()
    session.refresh(db_post)
    return db_post

def delete_post(session: Session, post_id: str) -> bool:
    """
    Delete a post by its unique identifier.
    
    Args:
        session (Session): Database session.
        post_id (str): The unique identifier of the post to delete.
    
    Returns:
        bool: True if deletion was successful, False otherwise.
    """
    db_post = get_post_by_id(session, post_id)
    if not db_post:
        return False

    session.delete(db_post)
    session.commit()
    return True

def list_posts(session: Session, offset: int = 0, limit: int = 100) -> List[Post]:
    """
    Retrieve a paginated list of posts.
    
    Args:
        session (Session): Database session.
        offset (int, optional): Number of posts to skip (for pagination). Defaults to 0.
        limit (int, optional): Maximum number of posts to return. Defaults to 100.
    
    Returns:
        List[Post]: A list of post objects.
    """
    statement = select(Post).offset(offset).limit(limit)
    return session.exec(statement).all()

