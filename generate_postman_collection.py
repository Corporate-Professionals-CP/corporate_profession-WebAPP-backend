import json
from datetime import datetime

# API documentation data
api_data = {
    "Authentication": [
        {"method": "GET", "path": "/api/auth/google/login", "name": "Google Login"},
        {"method": "GET", "path": "/api/auth/google/callback", "name": "Google Callback"},
        {"method": "POST", "path": "/api/auth/signup", "name": "Signup"},
        {"method": "POST", "path": "/api/auth/verify-email", "name": "Verify Email"},
        {"method": "POST", "path": "/api/auth/login", "name": "Login"},
        {"method": "POST", "path": "/api/auth/refresh-token", "name": "Refresh Token"},
        {"method": "POST", "path": "/api/auth/forgot-password", "name": "Forgot Password"},
        {"method": "POST", "path": "/api/auth/reset-password", "name": "Reset Password"}
    ],
    "Profiles": [
        {"method": "GET", "path": "/api/profiles/{user_id}", "name": "Get Profile"},
        {"method": "PUT", "path": "/api/profiles/{user_id}", "name": "Update Profile"},
        {"method": "GET", "path": "/api/profiles/me", "name": "Get Own Profile"},
        {"method": "GET", "path": "/api/profiles/{user_id}/completion", "name": "Get Profile Completion Status"},
        {"method": "POST", "path": "/api/profiles/{user_id}/cv", "name": "Upload Cv"},
        {"method": "DELETE", "path": "/api/profiles/{user_id}/cv", "name": "Delete Cv"},
        {"method": "GET", "path": "/api/profiles/{user_id}/cv", "name": "Download Cv"}
    ],
    "Directory": [
        {"method": "GET", "path": "/api/directory/", "name": "Search Directory"}
    ],
    "Posts": [
        {"method": "POST", "path": "/api/posts/", "name": "Create New Post"},
        {"method": "GET", "path": "/api/posts/feed/", "name": "Read Feed"},
        {"method": "POST", "path": "/api/posts/search", "name": "Search Posts Endpoint"},
        {"method": "GET", "path": "/api/posts/user/{user_id}", "name": "Read User Posts"},
        {"method": "GET", "path": "/api/posts/{post_id}", "name": "Read Post"},
        {"method": "PUT", "path": "/api/posts/{post_id}", "name": "Update Existing Post"},
        {"method": "DELETE", "path": "/api/posts/{post_id}", "name": "Delete Existing Post"}
    ],
    "Admin": [
        {"method": "PUT", "path": "/api/admin/dropdowns", "name": "Update Dropdowns"},
        {"method": "POST", "path": "/api/admin/users/{user_id}/deactivate", "name": "Deactivate User"},
        {"method": "POST", "path": "/api/admin/users/{user_id}/activate", "name": "Activate User"},
        {"method": "PATCH", "path": "/api/admin/posts/{post_id}/visibility", "name": "Toggle Post Visibility"},
        {"method": "GET", "path": "/api/admin/metrics", "name": "Get Admin Metrics"}
    ],
    "Feed": [
        {"method": "GET", "path": "/api/feed/", "name": "Get Personalized Feed"},
        {"method": "POST", "path": "/api/feed/", "name": "Create Post"}
    ]
}

# Create Postman collection structure
def create_postman_collection(api_data, collection_name="Corporate Professionals API"):
    collection = {
        "info": {
            "name": collection_name,
            "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
            "_postman_id": "a1b2c3d4-e5f6-7890-g1h2-i3j4k5l6m7n8",
            "description": "API collection for Corporate Professionals WebApp",
            "version": "1.0.0"
        },
        "item": []
    }

    for category, endpoints in api_data.items():
        folder = {
            "name": category,
            "item": []
        }

        for endpoint in endpoints:
            request = {
                "name": endpoint["name"],
                "request": {
                    "method": endpoint["method"],
                    "header": [],
                    "body": {
                        "mode": "raw",
                        "raw": "{}",
                        "options": {
                            "raw": {
                                "language": "json"
                            }
                        }
                    },
                    "url": {
                        "raw": "{{base_url}}" + endpoint["path"],
                        "host": ["{{base_url}}"],
                        "path": endpoint["path"].strip("/").split("/")
                    }
                },
                "response": []
            }

            # Add authentication header for endpoints that need it
            if category != "Authentication":
                request["request"]["header"].append({
                    "key": "Authorization",
                    "value": "Bearer {{auth_token}}",
                    "type": "text"
                })

            folder["item"].append(request)

        collection["item"].append(folder)

    # Add environment variables
    collection["variable"] = [
        {
            "key": "base_url",
            "value": "http://localhost:8000",
            "type": "string"
        },
        {
            "key": "auth_token",
            "value": "",
            "type": "string"
        }
    ]

    return collection

# Generate the collection
collection = create_postman_collection(api_data)

# Save to file
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
filename = f"corporate_professionals_api_{timestamp}.postman_collection.json"

with open(filename, "w") as f:
    json.dump(collection, f, indent=2)

print(f"Postman collection saved to {filename}")
