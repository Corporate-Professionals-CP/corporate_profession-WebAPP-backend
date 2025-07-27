import requests
import json

def test_custom_report_api():
    """Test the custom report API endpoint using requests"""
    
    # API endpoint
    base_url = "http://localhost:8001"  # Using port 8001 for testing
    endpoint = f"{base_url}/api/analytics/custom-report"
    
    # Admin user token - you'll need to get this from login or use existing token
    # For now, we'll create a token manually (replace with actual admin token)
    admin_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhMGY3NDYyZi01NzcxLTQ2YzMtODY3MS0yOWI0M2U3NTliZDMiLCJleHAiOjE3NTM3MjUzMDgsImlhdCI6MTc1MzYzODkwOCwidHlwZSI6ImFjY2VzcyIsInNjb3BlcyI6WyJ1c2VyIiwiYWRtaW4iXX0.AwykWrJKlXVh9IAcjutSejZrNXXh-1paFYdDc8V4kaI"  # Replace with actual token
    
    headers = {
        "Authorization": f"Bearer {admin_token}",
        "Content-Type": "application/json"
    }
    
    # Test payload with enum values
    payload = {
        "name": "maverick ibrahim",
        "time_range": "last_30_days",
        "metrics": ["user_metrics", "engagement_metrics", "content_analytics"],
        "export_format": "json"
    }
    
    print("Testing Custom Report API...")
    print(f"Endpoint: {endpoint}")
    print(f"Payload: {json.dumps(payload, indent=2)}")
    
    try:
        response = requests.post(endpoint, json=payload, headers=headers)
        
        print(f"\nResponse Status: {response.status_code}")
        
        if response.status_code == 200:
            response_data = response.json()
            print(f"Response Keys: {list(response_data.keys())}")
            
            # Check if data is present
            data = response_data.get('data', {})
            print(f"\nData Present: {bool(data)}")
            
            if data:
                print("Data Contents:")
                for key, value in data.items():
                    print(f"  - {key}: {type(value).__name__} ({len(str(value))} chars)")
            
            # Check summary
            summary = response_data.get('summary', {})
            print(f"\nSummary Present: {bool(summary)}")
            if summary:
                print(f"Summary Keys: {list(summary.keys())}")
                
        elif response.status_code == 401:
            print("Authentication failed - need valid admin token")
        elif response.status_code == 403:
            print("Access denied - need admin privileges")
        else:
            print(f"Error: {response.text}")
            
    except requests.exceptions.ConnectionError:
        print("Connection failed - make sure the server is running on http://localhost:8000")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    print("Note: Make sure your FastAPI server is running and you have a valid admin token")
    print("You can get an admin token by logging in through the /auth/login endpoint")
    test_custom_report_api()