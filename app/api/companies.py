from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_db
from app.core.security import get_current_active_user
from app.models.user import User
from app.models.company import Company
from app.schemas.company import (
    CompanyCreate, CompanyUpdate, CompanyResponse, 
    CompanySearchResponse, CompanyAdminCreate, CompanyAdminResponse
)
from app.crud.company import (
    create_company, get_company_by_id, get_company_by_username,
    update_company, delete_company, search_companies,
    follow_company, unfollow_company, add_company_admin,
    remove_company_admin, get_company_admins, get_company_followers,
    get_user_companies, is_company_admin, is_following_company
)

router = APIRouter(prefix="/companies", tags=["companies"])


@router.post("/", response_model=CompanyResponse, status_code=status.HTTP_201_CREATED)
async def create_new_company(
    company_data: CompanyCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Create a new company page"""
    try:
        company = await create_company(db, company_data, current_user.id)
        return company
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to create company")


@router.get("/search", response_model=CompanySearchResponse)
async def search_companies_endpoint(
    query: Optional[str] = Query(None, description="Search query"),
    industry: Optional[str] = Query(None, description="Filter by industry"),
    company_type: Optional[str] = Query(None, description="Filter by company type"),
    location: Optional[str] = Query(None, description="Filter by location"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    db: AsyncSession = Depends(get_db)
):
    """Search companies with filters"""
    skip = (page - 1) * per_page
    result = search_companies(
        db, query=query, industry=industry, company_type=company_type,
        location=location, skip=skip, limit=per_page
    )
    return result


@router.get("/my-companies", response_model=List[CompanyResponse])
async def get_my_companies(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get companies where current user is admin"""
    companies = get_user_companies(db, current_user.id)
    return companies


@router.get("/{company_id}", response_model=CompanyResponse)
async def get_company(
    company_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get company by ID"""
    company = get_company_by_id(db, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    return company


@router.get("/username/{username}", response_model=CompanyResponse)
async def get_company_by_username_endpoint(
    username: str,
    db: AsyncSession = Depends(get_db),
):
    """Get company by username"""
    company = get_company_by_username(db, username)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    return company


@router.put("/{company_id}", response_model=CompanyResponse)
async def update_company_endpoint(
    company_id: str,
    company_data: CompanyUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Update company (admin only)"""
    try:
        company = update_company(db, company_id, company_data, current_user.id)
        if not company:
            raise HTTPException(status_code=404, detail="Company not found")
        return company
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to update company")


@router.delete("/{company_id}")
async def delete_company_endpoint(
    company_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Delete company (owner only)"""
    try:
        success = await delete_company(db, company_id, current_user.id)
        if not success:
            raise HTTPException(status_code=404, detail="Company not found")
        return {"message": "Company deleted successfully"}
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to delete company")


@router.post("/{company_id}/follow")
async def follow_company_endpoint(
    company_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Follow a company"""
    try:
        follow = follow_company(db, company_id, current_user.id)
        return {"message": "Successfully followed company", "follow_id": follow.id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to follow company")


@router.delete("/{company_id}/follow")
async def unfollow_company_endpoint(
    company_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Unfollow a company"""
    success = unfollow_company(db, company_id, current_user.id)
    if not success:
        raise HTTPException(status_code=404, detail="Not following this company")
    return {"message": "Successfully unfollowed company"}


@router.get("/{company_id}/following-status")
async def get_following_status(
    company_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Check if current user is following the company"""
    is_following = is_following_company(db, company_id, current_user.id)
    return {"is_following": is_following}


@router.post("/{company_id}/admins", response_model=CompanyAdminResponse)
async def add_company_admin_endpoint(
    company_id: str,
    admin_data: CompanyAdminCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Add admin to company (owner/admin only)"""
    try:
        admin = add_company_admin(
            db, company_id, current_user.id, 
            admin_data.user_id, admin_data.role
        )
        return admin
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to add admin")


@router.delete("/{company_id}/admins/{admin_user_id}")
async def remove_company_admin_endpoint(
    company_id: str,
    admin_user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Remove admin from company (owner only)"""
    try:
        success = remove_company_admin(db, company_id, current_user.id, admin_user_id)
        if not success:
            raise HTTPException(status_code=404, detail="Admin not found")
        return {"message": "Admin removed successfully"}
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to remove admin")


@router.get("/{company_id}/admins", response_model=List[CompanyAdminResponse])
async def get_company_admins_endpoint(
    company_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get all admins for a company"""
    admins = get_company_admins(db, company_id)
    return admins


@router.get("/{company_id}/followers")
async def get_company_followers_endpoint(
    company_id: str,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    """Get company followers"""
    skip = (page - 1) * per_page
    followers = get_company_followers(db, company_id, skip, per_page)
    return {
        "followers": followers,
        "page": page,
        "per_page": per_page
    }


@router.get("/{company_id}/admin-status")
async def get_admin_status(
    company_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Check if current user is admin of the company"""
    is_admin = is_company_admin(db, company_id, current_user.id)
    return {"is_admin": is_admin}