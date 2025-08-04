"""
Complete enumeration definitions for all application dropdowns and fixed options.
Aligns with  requirements.
"""

from enum import Enum

class Industry(str, Enum):
    """
    Industry categories for professional networking and job classification.
    Complete list of 181 industries.
    """
    ACCOUNTING = "Accounting"
    ACTUARY = "Actuary"
    AGRICULTURE = "Agriculture"
    AIRLINES_AVIATION_AEROSPACE = "Airlines/Aviation/Aerospace"
    ALTERNATIVE_CAPITAL = "Alternative Capital"
    ALTERNATIVE_DISPUTE_RESOLUTION = "Alternative Dispute Resolution"
    ALTERNATIVE_MEDICINE = "Alternative Medicine"
    ANIMATION = "Animation"
    APPAREL_FASHION = "Apparel & Fashion"
    ARCHITECTURE_PLANNING = "Architecture & Planning"
    ARTS_AND_CRAFTS = "Arts and Crafts"
    AUTOMOTIVE = "Automotive"
    AVIATION_AEROSPACE = "Aviation & Aerospace"
    BANKING = "Banking"
    BEAUTY = "Beauty"
    BIOTECHNOLOGY = "Biotechnology"
    BROADCAST_MEDIA = "Broadcast Media"
    STOCK_BROKING = "Stock Broking"
    BUILDING_MATERIALS = "Building Materials"
    BUSINESS_SUPPLIES_AND_EQUIPMENT = "Business Supplies and Equipment"
    CAPITAL_MARKETS = "Capital Markets"
    CAPTIVES = "Captives"
    CHEMICALS = "Chemicals"
    CIVIC_SOCIAL_ORGANISATION = "Civic & Social Organisation"
    CIVIL_ENGINEERING = "Civil Engineering"
    CLAIMS = "Claims"
    CLIMATE = "Climate"
    COMMERCIAL_REAL_ESTATE = "Commercial Real Estate"
    COMPUTER_NETWORK_SECURITY = "Computer & Network Security"
    COMPUTER_GAMES = "Computer Games"
    COMPUTER_HARDWARE = "Computer Hardware"
    COMPUTER_NETWORKING = "Computer Networking"
    COMPUTER_SOFTWARE = "Computer Software"
    CONSTRUCTION = "Construction"
    CONSULTING = "Consulting"
    CONSUMER_ELECTRONICS = "Consumer Electronics"
    CONSUMER_GOODS = "Consumer Goods"
    CONSUMER_SERVICES = "Consumer Services"
    COSMETICS = "Cosmetics"
    CYBER = "Cyber"
    DAIRY = "Dairy"
    DEFENSE_SPACE = "Defense & Space"
    DESIGN = "Design"
    DIRECTORS_OFFICERS = "Directors & Officers"
    E_LEARNING = "E-Learning"
    EDUCATION_MANAGEMENT = "Education Management"
    ELECTRICAL_ELECTRONIC_MANUFACTURING = "Electrical/Electronic Manufacturing"
    EMERGING_MARKETS = "Emerging Markets"
    EMERGING_RISKS = "Emerging Risks"
    ENTERTAINMENT = "Entertainment"
    ENVIRONMENTAL_SERVICES = "Environmental Services"
    EVENTS_SERVICES = "Events Services"
    ESG = "ESG"
    EXECUTIVE_OFFICE = "Executive Office"
    FASHION = "Fashion"
    FACILITIES_SERVICES = "Facilities Services"
    FARMING = "Farming"
    FINANCIAL_LINES = "Financial Lines"
    FINANCIAL_SERVICES = "Financial Services"
    FINE_ART = "Fine Art"
    FISHERY = "Fishery"
    FOOD_BEVERAGES = "Food & Beverages"
    FOOD_PRODUCTION = "Food Production"
    FUND_RAISING = "Fund-Raising"
    FURNITURE = "Furniture"
    GAMBLING_CASINOS = "Gambling & Casinos"
    GLASS_CERAMICS_CONCRETE = "Glass, Ceramics & Concrete"
    GOVERNMENT_ADMINISTRATION = "Government Administration"
    GOVERNMENT_RELATIONS = "Government Relations"
    GRAPHIC_DESIGN = "Graphic Design"
    HEALTH_WELLNESS_FITNESS = "Health, Wellness and Fitness"
    HIGHER_EDUCATION = "Higher Education"
    HOSPITAL_HEALTH_CARE = "Hospital & Health Care"
    HOSPITALITY = "Hospitality"
    HUMAN_RESOURCES = "Human Resources"
    SOCIAL_WORKER = "Social Worker"
    IMPORT_EXPORT = "Import and Export"
    INDIVIDUAL_FAMILY_SERVICES = "Individual & Family Services"
    INDUSTRIAL_AUTOMATION = "Industrial Automation"
    INFORMATION_SERVICES = "Information Services"
    INFORMATION_TECHNOLOGY_SERVICES = "Information Technology and Services"
    INSURANCE = "Insurance"
    INTERNATIONAL_AFFAIRS = "International Affairs"
    INTERNATIONAL_TRADE_DEVELOPMENT = "International Trade and Development"
    INTERNET = "Internet"
    INVESTMENT_BANKING = "Investment Banking"
    INVESTMENT_MANAGEMENT = "Investment Management"
    JUDICIARY = "Judiciary"
    KIDNAP_RANSOM = "Kidnap & Ransom"
    LAW = "Law"
    LEISURE_TRAVEL_TOURISM = "Leisure Travel & Tourism"
    LIABILITY = "Liability"
    LIBRARIES = "Libraries"
    LOGISTICS_SUPPLY_CHAIN = "Logistics and Supply Chain"
    LUXURY_GOODS_JEWELRY = "Luxury Goods & Jewelry"
    MACHINERY = "Machinery"
    MANAGEMENT_CONSULTING = "Management Consulting"
    MARINE_CARGO = "Marine Cargo"
    MARINE_HULL = "Marine Hull"
    MARITIME = "Maritime"
    MARKET_RESEARCH = "Market Research"
    MARKETING_ADVERTISING = "Marketing and Advertising"
    ENGINEERING = "Engineering"
    MEDIA_PRODUCTION = "Media Production"
    MEDICAL_DEVICES = "Medical Devices"
    MEDICAL_PRACTICE = "Medical Practice"
    MENTAL_HEALTH_CARE = "Mental Health Care"
    MILITARY = "Military"
    MINING = "Mining"
    MINING_METALS = "Mining & Metals"
    MOTION_PICTURES_FILM = "Motion Pictures and Film"
    MUSEUMS_INSTITUTIONS = "Museums and Institutions"
    MUSIC = "Music"
    NANOTECHNOLOGY = "Nanotechnology"
    NEWSPAPERS = "Newspapers"
    NONPROFIT_ORGANISATION_MANAGEMENT = "Nonprofit Organisation Management"
    OFFSHORE_ENERGY = "Offshore Energy"
    OIL_ENERGY = "Oil & Energy"
    ONLINE_MEDIA = "Online Media"
    ONSHORE_ENERGY = "Onshore Energy"
    OPERATIONS = "Operations"
    OTHER = "Other"
    OUTSOURCING_OFFSHORING = "Outsourcing/Offshoring"
    PACKAGE_FREIGHT_DELIVERY = "Package/Freight Delivery"
    PACKAGING_CONTAINERS = "Packaging and Containers"
    PAPER_FOREST_PRODUCTS = "Paper & Forest Products"
    PARAMETRICS = "Parametrics"
    PERFORMING_ARTS = "Performing Arts"
    PHARMACEUTICALS = "Pharmaceuticals"
    PHILANTHROPY = "Philanthropy"
    PHOTOGRAPHY = "Photography"
    PLASTICS = "Plastics"
    POLITICAL_ORGANISATION = "Political Organisation"
    POLITICS = "Politics"
    PRIMARY_SECONDARY_EDUCATION = "Primary/Secondary Education"
    PRINTING = "Printing"
    PRODUCT_RECALL = "Product Recall"
    PROFESSIONAL_INDEMNITY_EO = "Professional Indemnity (E&O)"
    PROFESSIONAL_TRAINING_COACHING = "Professional Training & Coaching"
    PROGRAMME_DEVELOPMENT = "Programme Development"
    PROPERTY = "Property"
    PUBLIC_POLICY = "Public Policy"
    PUBLIC_RELATIONS_COMMUNICATIONS = "Public Relations and Communications"
    PUBLIC_SAFETY = "Public Safety"
    PUBLISHING = "Publishing"
    RAILROAD_MANUFACTURE = "Railroad Manufacture"
    RANCHING = "Ranching"
    REAL_ESTATE = "Real Estate"
    RECREATIONAL_FACILITIES_SERVICES = "Recreational Facilities and Services"
    REINSURANCE = "Reinsurance"
    RELIGIOUS_INSTITUTIONS = "Religious Institutions"
    RENEWABLES_ENVIRONMENT = "Renewables & Environment"
    RESEARCH = "Research"
    RESTAURANTS = "Restaurants"
    RETAIL = "Retail"
    SECURITY_INVESTIGATIONS = "Security and Investigations"
    SEMICONDUCTORS = "Semiconductors"
    STUDENT = "Student"
    SHIPBUILDING = "Shipbuilding"
    STEM = "STEM"
    SPORTING_GOODS = "Sporting Goods"
    SPORTS = "Sports"
    STAFFING_RECRUITING = "Staffing and Recruiting"
    SUPERMARKETS = "Supermarkets"
    TELECOMMUNICATIONS = "Telecommunications"
    TEACHER = "Teacher"
    TEXTILES = "Textiles"
    THINK_TANKS = "Think Tanks"
    TOBACCO = "Tobacco"
    TRANSLATION_LOCALISATION = "Translation and Localisation"
    TRANSPORTATION_TRUCKING_RAILROAD = "Transportation/Trucking/Railroad"
    UNDERWRITING = "Underwriting"
    UTILITIES = "Utilities"
    VENTURE_CAPITAL_PRIVATE_EQUITY = "Venture Capital & Private Equity"
    VETERINARY = "Veterinary"
    WAREHOUSING = "Warehousing"
    WHOLESALE = "Wholesale"
    WINE_SPIRITS = "Wine and Spirits"
    WRITING_EDITING = "Writing and Editing"

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
    def _missing_(cls, value):
        # Handle case-insensitive lookup
        if isinstance(value, str):
            # Convert input to lowercase and compare with lowercase enum values
            value = value.lower()
            for member in cls:
                if member.value.lower() == value:
                    return member
        return None

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
