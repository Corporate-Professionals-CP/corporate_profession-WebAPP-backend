"""
Complete enumeration definitions for all application dropdowns and fixed options.
Aligns with  requirements.
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
    MODERATOR = "Moderator"
    ADMIN = "Admin"

    @classmethod
    def list(cls):
        return [item.value for item in cls]

class ContactType(str, Enum):
    """
    contact selction setup
    User Profile
    """

    EMAIL = "email"
    LINKEDIN = "linkedin"
    X = "x"
    GITHUB = "github"
    WEBSITE = "website"
    CUSTOM = "custom"

    @classmethod
    def list(cls):
        return [item.value for item in cls]

class EmploymentType(str, Enum):
    """
    Work experience employment type
    """
    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    CONTRACT = "contract"
    FREELANCE = "freelance"
    INTERNSHIP = "internship"
    REMOTE = "remote"

    @classmethod
    def list(cls):
        return [item.value for item in cls]


class NotificationType(str, Enum):
    NEW_FOLLOWER = "new_follower"
    POST_COMMENT = "post_comment"
    POST_REACTION = "post_reaction"
    POST_TAG = "post_tag"
    BOOKMARK = "bookmark"
    JOB_APPLICATION = "job_application"
    NEW_MESSAGE = "new_message"
    POST_REPOST = "post_repost"
    CONNECTION_REQUEST = "connection_request"
    CONNECTION_ACCEPTED = "connection_accepted"

    @classmethod
    def list(cls):
        return [item.value for item in cls]

class ConnectionStatus(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"

    @classmethod
    def list(cls):
        return [item.value for item in cls]
