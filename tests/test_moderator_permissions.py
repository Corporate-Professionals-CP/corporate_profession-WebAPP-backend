import pytest
from httpx import AsyncClient
from uuid import uuid4
from app.main import app
from app.models.user import User
from app.models.reports import Report, ReportStatus, ReportType, ContentType, ReportPriority
from app.core.security import create_access_token

@pytest.mark.asyncio
async def test_moderator_can_view_reports(client: AsyncClient, test_db, test_user):
    # Make test user a moderator
    test_user.is_moderator = True
    test_db.add(test_user)
    await test_db.commit()
    await test_db.refresh(test_user)
    
    # Create moderator token
    moderator_token = create_access_token(str(test_user.id), scopes=["moderator"])
    
    # Test viewing reports
    response = await client.get(
        "/api/reports/",
        headers={"Authorization": f"Bearer {moderator_token}"}
    )
    
    assert response.status_code == 200
    assert "reports" in response.json()

@pytest.mark.asyncio
async def test_moderator_can_resolve_report(client: AsyncClient, test_db, test_user, admin_user):
    # Make test user a moderator
    test_user.is_moderator = True
    test_db.add(test_user)
    await test_db.commit()
    await test_db.refresh(test_user)
    
    # Create a test report
    report = Report(
        reporter_id=admin_user.id,
        reported_user_id=str(uuid4()),
        content_type=ContentType.USER_PROFILE,
        report_type=ReportType.INAPPROPRIATE_CONTENT,
        title="Test Report",
        description="Test Description",
        priority=ReportPriority.MEDIUM,
        status=ReportStatus.OPEN
    )
    test_db.add(report)
    await test_db.commit()
    await test_db.refresh(report)
    
    # Create moderator token
    moderator_token = create_access_token(str(test_user.id), scopes=["moderator"])
    
    # Test resolving report
    response = await client.post(
        f"/api/reports/{report.id}/resolve",
        json={"resolution_notes": "Resolved by moderator"},
        headers={"Authorization": f"Bearer {moderator_token}"}
    )
    
    assert response.status_code == 200
    assert "report_id" in response.json()
    
    # Verify report status in database
    updated_report = await test_db.get(Report, report.id)
    assert updated_report.status == ReportStatus.RESOLVED
    assert updated_report.resolver_id == test_user.id

@pytest.mark.asyncio
async def test_moderator_can_escalate_report(client: AsyncClient, test_db, test_user, admin_user):
    # Make test user a moderator
    test_user.is_moderator = True
    test_db.add(test_user)
    await test_db.commit()
    await test_db.refresh(test_user)
    
    # Create a test report
    report = Report(
        reporter_id=admin_user.id,
        reported_user_id=str(uuid4()),
        content_type=ContentType.USER_PROFILE,
        report_type=ReportType.INAPPROPRIATE_CONTENT,
        title="Test Report",
        description="Test Description",
        priority=ReportPriority.MEDIUM,
        status=ReportStatus.OPEN
    )
    test_db.add(report)
    await test_db.commit()
    await test_db.refresh(report)
    
    # Create moderator token
    moderator_token = create_access_token(str(test_user.id), scopes=["moderator"])
    
    # Test escalating report
    response = await client.post(
        f"/api/reports/{report.id}/escalate",
        json={
            "escalated_to": admin_user.id,
            "escalation_reason": "Needs admin attention"
        },
        headers={"Authorization": f"Bearer {moderator_token}"}
    )
    
    assert response.status_code == 200
    assert "report_id" in response.json()
    
    # Verify report status in database
    updated_report = await test_db.get(Report, report.id)
    assert updated_report.status == ReportStatus.ESCALATED
    assert updated_report.escalated_to == admin_user.id

@pytest.mark.asyncio
async def test_regular_user_cannot_access_reports(client: AsyncClient, test_db, test_user):
    # Create regular user token
    user_token = create_access_token(str(test_user.id), scopes=["user"])
    
    # Test viewing reports
    response = await client.get(
        "/api/reports/",
        headers={"Authorization": f"Bearer {user_token}"}
    )
    
    assert response.status_code == 403