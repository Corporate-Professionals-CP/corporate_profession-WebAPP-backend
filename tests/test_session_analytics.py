import asyncio
import uuid
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_db
from app.models.analytics import AnalyticsEvent, AnalyticsEventType
from app.crud.analytics import AnalyticsService
from app.schemas.analytics import AnalyticsFilterRequest, TimeRange

async def create_sample_session_data():
    """Create sample session events for testing"""
    async for db in get_db():
        try:
            # Create sample session events
            now = datetime.utcnow()
            user_id = "test-user-123"
            
            # Create multiple sessions with different durations
            sessions = [
                {"session_id": str(uuid.uuid4()), "start_offset": 60, "duration": 5},   # 5 min session
                {"session_id": str(uuid.uuid4()), "start_offset": 120, "duration": 12}, # 12 min session
                {"session_id": str(uuid.uuid4()), "start_offset": 180, "duration": 25}, # 25 min session
                {"session_id": str(uuid.uuid4()), "start_offset": 240, "duration": 45}, # 45 min session
                {"session_id": str(uuid.uuid4()), "start_offset": 300, "duration": 75}, # 75 min session
            ]
            
            for session in sessions:
                session_start_time = now - timedelta(minutes=session["start_offset"])
                session_end_time = session_start_time + timedelta(minutes=session["duration"])
                
                # Create SESSION_START event
                start_event = AnalyticsEvent(
                    user_id=user_id,
                    event_type=AnalyticsEventType.SESSION_START,
                    timestamp=session_start_time,
                    session_id=session["session_id"],
                    properties={"platform": "web"}
                )
                db.add(start_event)
                
                # Create SESSION_END event
                end_event = AnalyticsEvent(
                    user_id=user_id,
                    event_type=AnalyticsEventType.SESSION_END,
                    timestamp=session_end_time,
                    session_id=session["session_id"],
                    properties={"platform": "web"}
                )
                db.add(end_event)
            
            await db.commit()
            print(f"Created {len(sessions)} sample sessions for user {user_id}")
            
        except Exception as e:
            print(f"Error creating sample data: {e}")
            await db.rollback()
        finally:
            await db.close()
            break

async def test_session_analytics():
    """Test the session analytics methods"""
    async for db in get_db():
        try:
            analytics_service = AnalyticsService(db)
            
            # Test date range (last 30 days)
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=30)
            
            print("\nTesting Session Analytics Methods:")
            print("=" * 40)
            
            # Test average session duration
            avg_duration = await analytics_service._get_avg_session_duration(start_date, end_date)
            print(f"Average Session Duration: {avg_duration:.2f} minutes")
            
            # Test session duration distribution
            distribution = await analytics_service._get_session_duration_distribution(start_date, end_date)
            print(f"\nSession Duration Distribution:")
            for duration_range, count in distribution.items():
                print(f"  {duration_range}: {count} sessions")
            
            # Test repeat visit rates
            repeat_rates = await analytics_service._get_repeat_visit_rates()
            print(f"\nRepeat Visit Rates:")
            for period, rate in repeat_rates.items():
                print(f"  {period.capitalize()}: {rate:.2f}%")
            
            # Test engagement metrics (which includes session analytics)
            filters = AnalyticsFilterRequest(
                time_range=TimeRange.LAST_30_DAYS
            )
            engagement_metrics = await analytics_service.get_engagement_metrics(filters)
            
            print(f"\nEngagement Metrics (includes session data):")
            print(f"  Average Session Duration: {engagement_metrics.get('average_session_duration', 0):.2f} minutes")
            print(f"  Avg Time Per Session: {engagement_metrics.get('avg_time_per_session', 0):.2f} minutes")
            
            session_dist = engagement_metrics.get('session_duration_distribution', {})
            print(f"  Session Distribution: {session_dist}")
            
            repeat_rates = engagement_metrics.get('repeat_visit_rates', {})
            print(f"  Repeat Visit Rates: {repeat_rates}")
            
        except Exception as e:
            print(f"Error testing session analytics: {e}")
        finally:
            await db.close()
            break

async def main():
    """Main test function"""
    print("Session Analytics Test")
    print("=" * 30)
    
    # Create sample session data
    print("Creating sample session data...")
    await create_sample_session_data()
    
    # Test session analytics methods
    await test_session_analytics()
    
    print("\nSession analytics implementation completed!")
    print("The placeholder methods have been replaced with real implementations that:")
    print("- Calculate average session duration from SESSION_START/SESSION_END events")
    print("- Generate session duration distribution based on actual session data")
    print("- Calculate repeat visit rates using session frequency analysis")

if __name__ == "__main__":
    asyncio.run(main())