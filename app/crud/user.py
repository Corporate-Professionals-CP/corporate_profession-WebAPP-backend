from typing import Optional, List
from sqlmodel import Session, select
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate

def create_user(session: Session, user_data: UserCreate) -> User:
    """
    Create a new user in the database.
    
    Args:
        session (Session): Database session.
        user_data (UserCreate): Data for creating a user.
    
    Returns:
        User: The newly created user object.
    """
    db_user = User.from_orm(user_data)
    session.add(db_user)
    session.commit()
    session.refresh(db_user)
    return db_user

def get_user_by_id(session: Session, user_id: str) -> Optional[User]:
    """
    Retrieve a user by their unique ID.
    
    Args:
        session (Session): Database session.
        user_id (str): The unique identifier of the user.
    
    Returns:
        Optional[User]: The user if found, otherwise None.
    """
    statement = select(User).where(User.id == user_id)
    return session.exec(statement).first()

def get_user_by_email(session: Session, email: str) -> Optional[User]:
    """
    Retrieve a user by their email address.
    
    Args:
        session (Session): Database session.
        email (str): The user's email address.
    
    Returns:
        Optional[User]: The user if found, otherwise None.
    """
    statement = select(User).where(User.email == email)
    return session.exec(statement).first()

def update_user(session: Session, user_id: str, user_update: UserUpdate) -> Optional[User]:
    """
    Update an existing user's information.
    
    Args:
        session (Session): Database session.
        user_id (str): The unique identifier of the user to update.
        user_update (UserUpdate): The update payload with new data.
    
    Returns:
        Optional[User]: The updated user if found, otherwise None.
    """
    db_user = get_user_by_id(session, user_id)
    if not db_user:
        return None

    update_data = user_update.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_user, key, value)

    session.add(db_user)
    session.commit()
    session.refresh(db_user)
    return db_user

def delete_user(session: Session, user_id: str) -> bool:
    """
    Delete a user by their unique ID.
    
    Args:
        session (Session): Database session.
        user_id (str): The unique identifier of the user to delete.
    
    Returns:
        bool: True if deletion was successful, otherwise False.
    """
    db_user = get_user_by_id(session, user_id)
    if not db_user:
        return False

    session.delete(db_user)
    session.commit()
    return True

def list_users(session: Session, offset: int = 0, limit: int = 100) -> List[User]:
    """
    Retrieve a paginated list of users.
    
    Args:
        session (Session): Database session.
        offset (int, optional): Number of records to skip. Defaults to 0.
        limit (int, optional): Maximum number of records to return. Defaults to 100.
    
    Returns:
        List[User]: A list of users.
    """
    statement = select(User).offset(offset).limit(limit)
    return session.exec(statement).all()

