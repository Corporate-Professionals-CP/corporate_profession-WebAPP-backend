import asyncio
import sys
sys.path.append('app')

from db.database import get_db
from crud.analytics import AnalyticsService
from schemas.analytics import AnalyticsFilterRequest, TimeRange, CustomReportRequest
from api.analytics import _generate_report_summary
from datetime import datetime

async def test_custom_report():
    async for db in get_db():
        try:
            # Create analytics service
            analytics_service = AnalyticsService(db)
            
            # Create filters
            filters = AnalyticsFilterRequest(time_range=TimeRange.LAST_30_DAYS)
            
            # Test the same logic as the custom report endpoint
            metrics_to_include = ["user_metrics", "engagement_metrics", "content_analytics"]
            
            print("Generating report data...")
            report_data = {}
            
            if "user_metrics" in metrics_to_include:
                print("Getting user metrics...")
                user_metrics = await analytics_service.get_user_metrics(filters)
                report_data["user_metrics"] = user_metrics
                print(f"User metrics: {user_metrics}")
            
            if "engagement_metrics" in metrics_to_include:
                print("\nGetting engagement metrics...")
                engagement_metrics = await analytics_service.get_engagement_metrics(filters)
                report_data["engagement_metrics"] = engagement_metrics
                print(f"Engagement metrics: {engagement_metrics}")
            
            if "content_analytics" in metrics_to_include:
                print("\nGetting content analytics...")
                content_analytics = await analytics_service.get_content_analytics(filters)
                report_data["content_analytics"] = content_analytics
                print(f"Content analytics: {content_analytics}")
            
            print("\nGenerating summary...")
            summary = await _generate_report_summary(report_data, filters)
            print(f"Summary: {summary}")
            
            print("\n=== FINAL REPORT DATA ===")
            print(f"Report data keys: {list(report_data.keys())}")
            print(f"Report data empty? {not bool(report_data)}")
            
            for key, value in report_data.items():
                print(f"{key}: {type(value)} - Empty? {not bool(value)}")
                if isinstance(value, dict):
                    print(f"  Keys: {list(value.keys())}")
                    for k, v in value.items():
                        print(f"    {k}: {v}")
            
        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()
        break

if __name__ == "__main__":
    asyncio.run(test_custom_report())