from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.contact import Contact
from app.models.user import User
from app.schemas.contact import ContactCreate, ContactUpdate
from app.core.exceptions import CustomHTTPException
from pydantic import HttpUrl

# Create a contact
async def create_contact(session: AsyncSession, user: User, data: ContactCreate) -> Contact:
    try:
        contact = Contact(
            user_id=str(user.id),
            type=data.type,
            platform_name=data.platform_name,
            username=data.username,
            url=str(data.url),  # <-- important
        )
        session.add(contact)
        await session.commit()
        await session.refresh(contact)
        return contact
    except Exception as e:
        raise CustomHTTPException(status_code=500, detail=f"Error creating contact: {str(e)}")


# Get all contacts for a user
async def get_user_contacts(session: AsyncSession, user_id: str):
    try:
        result = await session.execute(select(Contact).where(Contact.user_id == user_id))
        contacts = result.scalars().all()
        return contacts  # returns [] if none found
    except Exception as e:
        raise CustomHTTPException(status_code=500, detail=f"Error retrieving contacts: {str(e)}")

# Update a contact
async def update_contact(session: AsyncSession, contact_id: str, data: ContactUpdate):
    try:
        contact = await session.get(Contact, contact_id)
        if not contact:
            raise CustomHTTPException(status_code=404, detail="Contact not found")
        
        for field, value in data.dict(exclude_unset=True).items():
            if field == "url" and isinstance(value, HttpUrl):
                value = str(value)
            setattr(contact, field, value)

        session.add(contact)
        await session.commit()
        await session.refresh(contact)
        return contact
    except Exception as e:
        raise CustomHTTPException(status_code=500, detail=f"Error updating contact: {str(e)}")


# Delete a contact
async def delete_contact(session: AsyncSession, contact_id: str):
    try:
        contact = await session.get(Contact, contact_id)
        if not contact:
            raise CustomHTTPException(status_code=404, detail="Contact not found")
        await session.delete(contact)
        await session.commit()
        return True
    except Exception as e:
        raise CustomHTTPException(status_code=500, detail=f"Error deleting contact: {str(e)}")

