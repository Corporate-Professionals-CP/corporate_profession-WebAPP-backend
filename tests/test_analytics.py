import asyncio
import sys
sys.path.append('app')

from db.database import get_db
from crud.analytics import AnalyticsService
from schemas.analytics import AnalyticsFilterRequest, TimeRange

async def test_analytics():
    async for db in get_db():
        try:
            service = AnalyticsService(db)
            filters = AnalyticsFilterRequest(time_range=TimeRange.LAST_30_DAYS)
            
            print("Testing user metrics...")
            user_metrics = await service.get_user_metrics(filters)
            print(f"User metrics: {user_metrics}")
            
            print("\nTesting engagement metrics...")
            engagement_metrics = await service.get_engagement_metrics(filters)
            print(f"Engagement metrics: {engagement_metrics}")
            
            print("\nTesting content analytics...")
            content_analytics = await service.get_content_analytics(filters)
            print(f"Content analytics: {content_analytics}")
            
        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()
        break

if __name__ == "__main__":
    asyncio.run(test_analytics())