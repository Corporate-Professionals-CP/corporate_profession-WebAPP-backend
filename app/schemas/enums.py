"""
Complete enumeration definitions for all application dropdowns and fixed options.
Aligns with PRD section 2.2 requirements.
"""

from enum import Enum

class Industry(str, Enum):
    """
    Industry classification for professionals.
    Reference: Section Profile fields
    """
    TECHNOLOGY = "Technology"
    FINANCE = "Finance"
    HEALTHCARE = "Healthcare"
    EDUCATION = "Education"
    MANUFACTURING = "Manufacturing"
    CONSULTING = "Consulting"
    GOVERNMENT = "Government"
    NONPROFIT = "Nonprofit"
    OTHER = "Other"

    @classmethod
    def list(cls):
        return [item.value for item in cls]

class ExperienceLevel(str, Enum):
    """
    Professional experience ranges.
    Reference: Years of Experience
    """
    ENTRY = "0-2 years"
    MID = "3-5 years"
    SENIOR = "6-10 years"
    EXPERT = "10+ years"

    @classmethod
    def list(cls):
        return [item.value for item in cls]

class EducationLevel(str, Enum):
    """
    Highest education attainment.
    Reference: Education
    """
    HIGH_SCHOOL = "High School"
    ASSOCIATE = "Associate Degree"
    BACHELORS = "Bachelor's Degree"
    MASTERS = "Master's Degree"
    DOCTORATE = "PhD/Doctorate"
    PROFESSIONAL = "Professional Certification"
    OTHER = "Other"

    @classmethod
    def list(cls):
        return [item.value for item in cls]

class Gender(str, Enum):
    """
    Gender identity options with inclusive default.
    Sex
    """
    MALE = "Male"
    FEMALE = "Female"
    NON_BINARY = "Non-binary"
    PREFER_NOT_TO_SAY = "Prefer not to say"
    OTHER = "Other"

    @classmethod
    def list(cls):
        return [item.value for item in cls]

class ProfileVisibility(str, Enum):
    """
    Profile visibility settings for GDPR compliance.
    Hide Profile
    """
    PUBLIC = "Public"  # All profile details visible
    PRIVATE = "Private"  # Only name and basic info visible
    HIDDEN = "Hidden"  # Completely hidden from searches

    @classmethod
    def list(cls):
        return [item.value for item in cls]

class JobTitle(str, Enum):
    """
    Common professional job titles.
    Job Title dropdown
    """
    SOFTWARE_ENGINEER = "Software Engineer"
    BACKEND_DEVELOPER = "Backend Developer"
    FRONTEND_DEVELOPER = "Frontend Developer"
    DEVOPS_ENGINEER = "DevOps Engineer"
    PRODUCT_MANAGER = "Product Manager"
    DATA_SCIENTIST = "Data Scientist"
    UX_DESIGNER = "UX Designer"
    FINANCIAL_ANALYST = "Financial Analyst"
    MARKETING_DIRECTOR = "Marketing Director"
    HR_MANAGER = "HR Manager"
    SALES_EXECUTIVE = "Sales Executive"
    CEO = "Chief Executive Officer"
    CTO = "Chief Technology Officer"
    OTHER = "Other"

    @classmethod
    def list(cls):
        return [item.value for item in cls]

class Location(str, Enum):
    """
    Common locations (countries/states).
    Location dropdown
    """
    NIGERIA = "NIGERIA"
    UNITED_STATES = "United States"
    UNITED_KINGDOM = "United Kingdom"
    CANADA = "Canada"
    AUSTRALIA = "Australia"
    GERMANY = "Germany"
    FRANCE = "France"
    INDIA = "India"
    SINGAPORE = "Singapore"
    REMOTE = "Remote"
    OTHER = "Other"

    @classmethod
    def list(cls):
        return [item.value for item in cls]

class PostType(str, Enum):
    """
    Types of content posts users can create.
    Posting & Feed
    """
    JOB_POSTING = "Job Opportunity"
    INDUSTRY_NEWS = "Industry News"
    PROFESSIONAL_UPDATE = "Professional Update"
    QUESTION = "Question"
    DISCUSSION = "Discussion"
    OTHER = "Other"

    @classmethod
    def list(cls):
        return [item.value for item in cls]

class PostVisibility(str, Enum):
    """
    Controls who can see the post.
    Feed visibility
    """
    PUBLIC = "public"  # Visible to all users
    INDUSTRY = "industry"  # Only visible to same industry
    FOLLOWERS = "followers"  # Only visible to followers
    PRIVATE = "private"  # Only visible to creator

    @classmethod
    def list(cls):
        return [item.value for item in cls]


class UserRole(str, Enum):
    """
    System roles for access control.
    Admin Panel
    """
    STANDARD = "Standard"
    RECRUITER = "Recruiter"
    ADMIN = "Admin"

    @classmethod
    def list(cls):
        return [item.value for item in cls]
