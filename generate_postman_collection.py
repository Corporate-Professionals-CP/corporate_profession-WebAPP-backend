import json
from collections import defaultdict

# Define your API endpoints data structure
api_endpoints = [
    # Authentication
    {"method": "POST", "path": "/api/auth/login", "name": "Login"},
    {"method": "POST", "path": "/api/auth/token", "name": "Login"},
    {"method": "POST", "path": "/api/auth/google", "name": "Google Oauth"},
    {"method": "POST", "path": "/api/auth/signup", "name": "Signup"},
    {"method": "POST", "path": "/api/auth/signup/google", "name": "Signup With Google"},
    {"method": "POST", "path": "/api/auth/verify-email", "name": "Verify Email"},
    {"method": "POST", "path": "/api/auth/refresh-token", "name": "Refresh Token"},
    {"method": "POST", "path": "/api/auth/forgot-password", "name": "Forgot Password"},
    {"method": "POST", "path": "/api/auth/reset-password", "name": "Reset Password"},

    # Profiles
    {"method": "GET", "path": "/api/profiles/{user_id}", "name": "Get Profile"},
    {"method": "PUT", "path": "/api/profiles/{user_id}", "name": "Update Profile"},
    {"method": "GET", "path": "/api/profiles/me", "name": "Get Own Profile"},
    {"method": "GET", "path": "/api/profiles/{user_id}/completion", "name": "Get Profile Completion Status"},
    {"method": "POST", "path": "/api/profiles/{user_id}/cv", "name": "Upload Cv"},
    {"method": "DELETE", "path": "/api/profiles/{user_id}/cv", "name": "Delete Cv"},
    {"method": "GET", "path": "/api/profiles/{user_id}/cv", "name": "Download Cv"},

    # Directory
    {"method": "GET", "path": "/api/directory/", "name": "Search Directory"},

    # Posts
    {"method": "POST", "path": "/api/posts/", "name": "Create New Post"},
    {"method": "GET", "path": "/api/posts/feed/", "name": "Read Feed"},
    {"method": "POST", "path": "/api/posts/search", "name": "Search Posts Endpoint"},
    {"method": "GET", "path": "/api/posts/user/{user_id}", "name": "Read User Posts"},
    {"method": "GET", "path": "/api/posts/{post_id}", "name": "Read Post"},
    {"method": "PUT", "path": "/api/posts/{post_id}", "name": "Update Existing Post"},
    {"method": "DELETE", "path": "/api/posts/{post_id}", "name": "Delete Existing Post"},

    # Admin
    {"method": "GET", "path": "/api/admin/users", "name": "Admin List Users"},
    {"method": "POST", "path": "/api/admin/users/bulk-actions", "name": "Bulk User Actions"},
    {"method": "POST", "path": "/api/admin/users/{user_id}/deactivate", "name": "Deactivate User"},
    {"method": "POST", "path": "/api/admin/users/{user_id}/activate", "name": "Activate User"},
    {"method": "PUT", "path": "/api/admin/users/{user_id}", "name": "Admin Update User"},
    {"method": "GET", "path": "/api/admin/posts", "name": "Admin List Posts"},
    {"method": "PATCH", "path": "/api/admin/posts/{post_id}/visibility", "name": "Toggle Post Visibility"},
    {"method": "DELETE", "path": "/api/admin/posts/{post_id}", "name": "Admin Delete Post"},
    {"method": "GET", "path": "/api/admin/dropdowns", "name": "Get Dropdown Options"},
    {"method": "GET", "path": "/api/admin/metrics", "name": "Get Admin Metrics"},

    # Feed
    {"method": "GET", "path": "/api/feed/", "name": "Get Personalized Feed"},
    {"method": "POST", "path": "/api/feed/", "name": "Create Post"},
]

def create_postman_collection():
    # Create collection structure
    collection = {
        "info": {
            "name": "Cooperate Professionals API",
            "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
        },
        "item": []
    }

    # Group endpoints by category
    categories = defaultdict(list)
    for endpoint in api_endpoints:
        category = endpoint["path"].split("/")[2] if len(endpoint["path"].split("/")) > 2 else "root"
        categories[category.capitalize()].append(endpoint)

    # Create folders and requests
    for category, endpoints in categories.items():
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
                    "url": {
                        "raw": "{{base_url}}" + endpoint["path"],
                        "host": ["{{base_url}}"],
                        "path": endpoint["path"].split("/")[1:]
                    }
                },
                "response": []
            }
            folder["item"].append(request)
        
        collection["item"].append(folder)

    # Add variables
    collection["variable"] = [
        {
            "key": "base_url",
            "value": "http://localhost:8000",
            "type": "string"
        }
    ]

    return collection

# Generate and save the collection
if __name__ == "__main__":
    collection = create_postman_collection()
    with open("cooperate_professionals.postman_collection.json", "w") as f:
        json.dump(collection, f, indent=2)
    print("Postman collection generated successfully!")
