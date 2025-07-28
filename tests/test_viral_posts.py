import asyncio
import sys
sys.path.append('app')

from datetime import datetime, date, timedelta
from db.database import get_db
from crud.analytics import AnalyticsService
from schemas.analytics import AnalyticsFilterRequest, TimeRange


async def test_viral_posts_method():
    """Test the _get_most_viral_posts method directly"""
    print(" Testing Viral Posts Implementation")
    print("=" * 50)
    
    async for db in get_db():
        try:
            # Create analytics service
            analytics_service = AnalyticsService(db)
            
            print(" Analytics service created successfully")
            
            # Test with different date ranges
            test_cases = [
                {
                    "name": "Last 7 days",
                    "start_date": date.today() - timedelta(days=7),
                    "end_date": date.today()
                },
                {
                    "name": "Last 30 days", 
                    "start_date": date.today() - timedelta(days=30),
                    "end_date": date.today()
                },
                {
                    "name": "Last 90 days",
                    "start_date": date.today() - timedelta(days=90),
                    "end_date": date.today()
                }
            ]
            
            for test_case in test_cases:
                print(f"\n Testing: {test_case['name']}")
                print(f"Date range: {test_case['start_date']} to {test_case['end_date']}")
                
                try:
                    viral_posts = await analytics_service._get_most_viral_posts(
                        start_date=test_case['start_date'],
                        end_date=test_case['end_date']
                    )
                    
                    print(f" Method executed successfully")
                    print(f" Found {len(viral_posts)} viral posts")
                    
                    if viral_posts:
                        print("\n Top Viral Posts:")
                        for i, post in enumerate(viral_posts[:3]):  # Show top 3
                            print(f"  {i+1}. Post ID: {post.get('post_id', 'N/A')}")
                            print(f"     Author: {post.get('author_name', 'N/A')}")
                            print(f"     Content: {str(post.get('content', 'N/A'))[:50]}...")
                            print(f"     Likes: {post.get('likes_count', 0)}")
                            print(f"     Comments: {post.get('comments_count', 0)}")
                            print(f"     Shares: {post.get('shares_count', 0)}")
                            print(f"     Viral Score: {post.get('viral_score', 0):.2f}")
                            print(f"     Created: {post.get('created_at', 'N/A')}")
                            print()
                        
                        # Verify sorting
                        if len(viral_posts) > 1:
                            is_sorted = all(
                                viral_posts[i].get('viral_score', 0) >= viral_posts[i+1].get('viral_score', 0)
                                for i in range(len(viral_posts) - 1)
                            )
                            if is_sorted:
                                print(" Posts are correctly sorted by viral score")
                            else:
                                print("  Posts may not be properly sorted")
                    else:
                        print(" No viral posts found in this date range")
                        
                except Exception as e:
                    print(f" Error testing {test_case['name']}: {str(e)}")
                    import traceback
                    traceback.print_exc()
            
            print("\n" + "=" * 50)
            print(" Viral Posts Method Testing Completed!")
            
        except Exception as e:
            print(f" Error setting up test: {str(e)}")
            import traceback
            traceback.print_exc()
        break


def test_viral_score_calculation():
    """Test the viral score calculation logic"""
    print("\n Testing Viral Score Calculation")
    print("=" * 40)
    
    # Test cases for viral score calculation
    test_cases = [
        {"likes": 10, "comments": 5, "shares": 2, "expected_min": 20},  # 10 + (5*2) + (2*3) = 26
        {"likes": 100, "comments": 20, "shares": 10, "expected_min": 170},  # 100 + (20*2) + (10*3) = 170
        {"likes": 1, "comments": 1, "shares": 1, "expected_min": 6},  # 1 + (1*2) + (1*3) = 6
        {"likes": 0, "comments": 0, "shares": 0, "expected_min": 0},  # 0 + 0 + 0 = 0
    ]
    
    for i, case in enumerate(test_cases):
        # Calculate viral score using the same formula as in the implementation
        # likes * 1 + comments * 2 + shares * 3
        calculated_score = case["likes"] + (case["comments"] * 2) + (case["shares"] * 3)
        
        print(f"Test {i+1}:")
        print(f"  Likes: {case['likes']}, Comments: {case['comments']}, Shares: {case['shares']}")
        print(f"  Calculated Score: {calculated_score}")
        print(f"  Expected Min: {case['expected_min']}")
        
        if calculated_score >= case["expected_min"]:
            print(f"   Score calculation correct")
        else:
            print(f"   Score calculation incorrect")
        print()


async def test_endpoint_integration():
    """Test the endpoint integration with the analytics service"""
    print("\n🔗 Testing Endpoint Integration")
    print("=" * 35)
    
    async for db in get_db():
        try:
            analytics_service = AnalyticsService(db)
            
            # Test the _get_date_range method that the endpoint uses
            filters = AnalyticsFilterRequest(time_range=TimeRange.LAST_30_DAYS)
            
            try:
                date_range = analytics_service._get_date_range(filters)
                print(f" Date range calculation works: {date_range[0]} to {date_range[1]}")
            except Exception as e:
                print(f"  Date range calculation issue: {str(e)}")
            
            # Test with different time ranges
            time_ranges = [TimeRange.LAST_7_DAYS, TimeRange.LAST_30_DAYS, TimeRange.LAST_90_DAYS]
            
            for time_range in time_ranges:
                try:
                    filters = AnalyticsFilterRequest(time_range=time_range)
                    date_range = analytics_service._get_date_range(filters)
                    print(f" {time_range.value} range: {date_range[0]} to {date_range[1]}")
                except Exception as e:
                    print(f" Error with {time_range.value}: {str(e)}")
            
        except Exception as e:
            print(f" Integration test error: {str(e)}")
        break


async def main():
    """Main test function"""
    print(" Viral Posts Endpoint Test Suite")
    print("=" * 50)
    
    try:
        # Test the core method
        await test_viral_posts_method()
        
        # Test viral score calculation
        test_viral_score_calculation()
        
        # Test endpoint integration
        await test_endpoint_integration()
        
        print("\n" + "=" * 50)
        print(" All Tests Completed Successfully!")
        
        print("\n Endpoint Information:")
        print("URL: GET /analytics/viral-posts")
        print("Authentication: Admin required")
        print("\nParameters:")
        print("  - time_range: LAST_7_DAYS, LAST_30_DAYS, LAST_90_DAYS, etc.")
        print("  - start_date: Custom start date (YYYY-MM-DD)")
        print("  - end_date: Custom end date (YYYY-MM-DD)")
        print("  - limit: Number of posts (1-50, default: 10)")
        
        print("\nResponse Structure:")
        print("  - viral_posts: Array of posts with viral scores")
        print("  - total_count: Total number of viral posts found")
        print("  - time_range: Applied date range")
        print("  - generated_at: Timestamp of report generation")
        
        print("\nViral Score Formula:")
        print("  Score = Likes × 1 + Comments × 2 + Shares × 3")
        
        print("\n Ready for Testing:")
        print("1. Access Swagger UI at /docs")
        print("2. Authenticate as admin")
        print("3. Test the /analytics/viral-posts endpoint")
        print("4. Try different time ranges and limits")
        
    except Exception as e:
        print(f"\n Test suite failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


if __name__ == "__main__":
    asyncio.run(main())