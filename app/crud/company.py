from typing import List, Optional, Dict, Any
from sqlmodel import Session, select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.company import Company, CompanyAdmin, CompanyFollower
from app.models.user import User
from app.models.post import Post
from app.schemas.company import CompanyCreate, CompanyUpdate
from datetime import datetime


async def create_company(db: AsyncSession, company_data: CompanyCreate, creator_user_id: str) -> Company:
    """Create a new company and assign creator as owner"""
    # Check if username is already taken
    result = await db.exec(select(Company).where(Company.username == company_data.username))
    existing = result.first()
    if existing:
        raise ValueError(f"Company username '{company_data.username}' is already taken")
    
    # Create company
    company = Company(**company_data.model_dump())
    db.add(company)
    await db.flush()  # Get the company ID
    
    # Add creator as owner
    admin = CompanyAdmin(
        user_id=creator_user_id,
        company_id=company.id,
        role="owner",
        permissions={
            "can_edit_profile": True,
            "can_post": True,
            "can_manage_admins": True,
            "can_delete_company": True,
            "can_view_analytics": True
        }
    )
    db.add(admin)
    await db.commit()
    await db.refresh(company)
    return company


def get_company_by_id(db: Session, company_id: str) -> Optional[Company]:
    """Get company by ID"""
    return db.exec(select(Company).where(Company.id == company_id)).first()


def get_company_by_username(db: Session, username: str) -> Optional[Company]:
    """Get company by username"""
    return db.exec(select(Company).where(Company.username == username.lower())).first()


def update_company(db: Session, company_id: str, company_data: CompanyUpdate, user_id: str) -> Optional[Company]:
    """Update company (only by admins)"""
    # Check if user is admin
    admin = db.exec(
        select(CompanyAdmin).where(
            and_(
                CompanyAdmin.company_id == company_id,
                CompanyAdmin.user_id == user_id
            )
        )
    ).first()
    
    if not admin:
        raise ValueError("User is not authorized to update this company")
    
    company = get_company_by_id(db, company_id)
    if not company:
        return None
    
    # Update fields
    update_data = company_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(company, field, value)
    
    company.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(company)
    return company


async def delete_company(db: AsyncSession, company_id: str, user_id: str) -> bool:
    """Delete company (only by owner)"""
    # Check if user is owner
    result = await db.exec(
        select(CompanyAdmin).where(
            and_(
                CompanyAdmin.company_id == company_id,
                CompanyAdmin.user_id == user_id,
                CompanyAdmin.role == "owner"
            )
        )
    )
    admin = result.first()
    
    if not admin:
        raise ValueError("Only company owner can delete the company")
    
    result = await db.exec(select(Company).where(Company.id == company_id))
    company = result.first()
    if not company:
        return False
    
    await db.delete(company)
    await db.commit()
    return True


def search_companies(
    db: Session,
    query: Optional[str] = None,
    industry: Optional[str] = None,
    company_type: Optional[str] = None,
    location: Optional[str] = None,
    skip: int = 0,
    limit: int = 20
) -> Dict[str, Any]:
    """Search companies with filters"""
    statement = select(Company)
    
    conditions = []
    
    if query:
        conditions.append(
            or_(
                Company.name.ilike(f"%{query}%"),
                Company.username.ilike(f"%{query}%"),
                Company.description.ilike(f"%{query}%")
            )
        )
    
    if industry:
        conditions.append(Company.industry.ilike(f"%{industry}%"))
    
    if company_type:
        conditions.append(Company.company_type == company_type)
    
    if location:
        conditions.append(Company.location.ilike(f"%{location}%"))
    
    if conditions:
        statement = statement.where(and_(*conditions))
    
    # Get total count
    total_statement = select(func.count(Company.id))
    if conditions:
        total_statement = total_statement.where(and_(*conditions))
    total = db.exec(total_statement).first()
    
    # Get paginated results
    companies = db.exec(
        statement.order_by(Company.follower_count.desc(), Company.created_at.desc())
        .offset(skip)
        .limit(limit)
    ).all()
    
    return {
        "companies": companies,
        "total": total,
        "page": (skip // limit) + 1,
        "per_page": limit,
        "has_next": skip + limit < total,
        "has_prev": skip > 0
    }


def follow_company(db: Session, company_id: str, user_id: str) -> CompanyFollower:
    """Follow a company"""
    # Check if already following
    existing = db.exec(
        select(CompanyFollower).where(
            and_(
                CompanyFollower.company_id == company_id,
                CompanyFollower.user_id == user_id
            )
        )
    ).first()
    
    if existing:
        raise ValueError("Already following this company")
    
    # Check if company exists
    company = get_company_by_id(db, company_id)
    if not company:
        raise ValueError("Company not found")
    
    # Create follow relationship
    follow = CompanyFollower(company_id=company_id, user_id=user_id)
    db.add(follow)
    
    # Update follower count
    company.follower_count += 1
    
    db.commit()
    db.refresh(follow)
    return follow


def unfollow_company(db: Session, company_id: str, user_id: str) -> bool:
    """Unfollow a company"""
    follow = db.exec(
        select(CompanyFollower).where(
            and_(
                CompanyFollower.company_id == company_id,
                CompanyFollower.user_id == user_id
            )
        )
    ).first()
    
    if not follow:
        return False
    
    # Update follower count
    company = get_company_by_id(db, company_id)
    if company:
        company.follower_count = max(0, company.follower_count - 1)
    
    db.delete(follow)
    db.commit()
    return True


def add_company_admin(db: Session, company_id: str, user_id: str, new_admin_user_id: str, role: str) -> CompanyAdmin:
    """Add a new admin to company (only by owner or admin)"""
    # Check if user has permission
    admin = db.exec(
        select(CompanyAdmin).where(
            and_(
                CompanyAdmin.company_id == company_id,
                CompanyAdmin.user_id == user_id
            )
        )
    ).first()
    
    if not admin or admin.role not in ["owner", "admin"]:
        raise ValueError("User is not authorized to add admins")
    
    # Check if user is already admin
    existing = db.exec(
        select(CompanyAdmin).where(
            and_(
                CompanyAdmin.company_id == company_id,
                CompanyAdmin.user_id == new_admin_user_id
            )
        )
    ).first()
    
    if existing:
        raise ValueError("User is already an admin")
    
    # Create admin role
    permissions = {
        "can_edit_profile": role in ["owner", "admin"],
        "can_post": True,
        "can_manage_admins": role == "owner",
        "can_delete_company": role == "owner",
        "can_view_analytics": role in ["owner", "admin"]
    }
    
    new_admin = CompanyAdmin(
        user_id=new_admin_user_id,
        company_id=company_id,
        role=role,
        permissions=permissions
    )
    
    db.add(new_admin)
    db.commit()
    db.refresh(new_admin)
    return new_admin


def remove_company_admin(db: Session, company_id: str, user_id: str, admin_user_id: str) -> bool:
    """Remove admin from company (only by owner)"""
    # Check if user is owner
    admin = db.exec(
        select(CompanyAdmin).where(
            and_(
                CompanyAdmin.company_id == company_id,
                CompanyAdmin.user_id == user_id,
                CompanyAdmin.role == "owner"
            )
        )
    ).first()
    
    if not admin:
        raise ValueError("Only company owner can remove admins")
    
    # Find admin to remove
    admin_to_remove = db.exec(
        select(CompanyAdmin).where(
            and_(
                CompanyAdmin.company_id == company_id,
                CompanyAdmin.user_id == admin_user_id
            )
        )
    ).first()
    
    if not admin_to_remove:
        return False
    
    # Cannot remove owner
    if admin_to_remove.role == "owner":
        raise ValueError("Cannot remove company owner")
    
    db.delete(admin_to_remove)
    db.commit()
    return True


def get_company_admins(db: Session, company_id: str) -> List[CompanyAdmin]:
    """Get all admins for a company"""
    return db.exec(
        select(CompanyAdmin).where(CompanyAdmin.company_id == company_id)
    ).all()


def get_company_followers(db: Session, company_id: str, skip: int = 0, limit: int = 20) -> List[CompanyFollower]:
    """Get company followers"""
    return db.exec(
        select(CompanyFollower)
        .where(CompanyFollower.company_id == company_id)
        .order_by(CompanyFollower.followed_at.desc())
        .offset(skip)
        .limit(limit)
    ).all()


def get_user_companies(db: Session, user_id: str) -> List[Company]:
    """Get companies where user is admin"""
    admin_companies = db.exec(
        select(Company)
        .join(CompanyAdmin)
        .where(CompanyAdmin.user_id == user_id)
        .order_by(Company.created_at.desc())
    ).all()
    
    return admin_companies


def is_company_admin(db: Session, company_id: str, user_id: str) -> bool:
    """Check if user is admin of company"""
    admin = db.exec(
        select(CompanyAdmin).where(
            and_(
                CompanyAdmin.company_id == company_id,
                CompanyAdmin.user_id == user_id
            )
        )
    ).first()
    
    return admin is not None


def is_following_company(db: Session, company_id: str, user_id: str) -> bool:
    """Check if user is following company"""
    follow = db.exec(
        select(CompanyFollower).where(
            and_(
                CompanyFollower.company_id == company_id,
                CompanyFollower.user_id == user_id
            )
        )
    ).first()
    
    return follow is not None