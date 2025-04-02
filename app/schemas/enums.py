"""
Defines enumerations used throughout the application.
"""

from enum import Enum, StrEnum

class Industry(StrEnum):
    """
    Industry classification for professionals.
    """
    TECH = "Tech"
    FINANCE = "Finance"
    HEALTHCARE = "Healthcare"
    EDUCATION = "Education"
    OTHER = "Other"  # Added as for future expansion

    @classmethod
    def list(cls):
        """Returns list of all valid values for API validation"""
        return [item.value for item in cls]

class ExperienceLevel(StrEnum):
    """
    Professional experience ranges.
    """
    ENTRY = "0-2"
    MID = "3-5"
    SENIOR = "6-10"
    EXPERT = "10+"

    @classmethod
    def list(cls):
        return [item.value for item in cls]

class Gender(StrEnum):
    """
    Gender identity options with inclusive default.
    """
    MALE = "Male"
    FEMALE = "Female"
    OTHER = "Prefer not to say"

    @classmethod
    def list(cls):
        return [item.value for item in cls]