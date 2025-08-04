"""convert_industry_from_enum_to_string

Revision ID: 6eae0cbc8923
Revises: c0ec106d81ce
Create Date: 2025-08-04 16:28:52.578598

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "6eae0cbc8923"
down_revision = "c0ec106d81ce"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Convert industry enum to string in user table
    op.execute('ALTER TABLE "user" ALTER COLUMN industry TYPE VARCHAR(255) USING industry::text')
    
    # Convert industry enum to string in post table
    op.execute('ALTER TABLE "post" ALTER COLUMN industry TYPE VARCHAR(255) USING industry::text')
    
    # Drop the old industry enum type
    op.execute("DROP TYPE IF EXISTS industry CASCADE")


def downgrade() -> None:
    # Recreate the industry enum type with all 181 values
    industry_values = [
        'Accounting', 'Advertising', 'Aerospace', 'Agriculture', 'Airlines', 'Alternative Energy',
        'Animation', 'Apparel', 'Architecture', 'Arts and Crafts', 'Automotive', 'Aviation',
        'Banking', 'Biotechnology', 'Broadcasting', 'Building Materials', 'Business Services',
        'Capital Markets', 'Chemicals', 'Civil Engineering', 'Commercial Real Estate', 'Computer Games',
        'Computer Hardware', 'Computer Networking', 'Computer Software', 'Construction', 'Consumer Electronics',
        'Consumer Goods', 'Consumer Services', 'Cosmetics', 'Dairy', 'Defense', 'Design',
        'E-Learning', 'Education Management', 'Electrical', 'Entertainment', 'Environmental Services',
        'Events Services', 'Executive Office', 'Facilities Services', 'Farming', 'Fashion',
        'Financial Services', 'Fine Art', 'Fishery', 'Food and Beverages', 'Food Production',
        'Fund-Raising', 'Furniture', 'Gambling', 'Glass', 'Government Administration', 'Government Relations',
        'Graphic Design', 'Health', 'Higher Education', 'Hospital', 'Hospitality', 'Human Resources',
        'Import and Export', 'Individual', 'Industrial Automation', 'Information Services', 'Information Technology',
        'Insurance', 'International Affairs', 'International Trade', 'Internet', 'Investment Banking',
        'Investment Management', 'Judiciary', 'Law Enforcement', 'Law Practice', 'Legal Services',
        'Legislative Office', 'Leisure', 'Libraries', 'Logistics', 'Luxury Goods', 'Machinery',
        'Management Consulting', 'Maritime', 'Market Research', 'Marketing', 'Mechanical', 'Media Production',
        'Medical Devices', 'Medical Practice', 'Mental Health Care', 'Military', 'Mining', 'Motion Pictures',
        'Museums', 'Music', 'Nanotechnology', 'Newspapers', 'Non-Profit Organization Management', 'Nuclear Energy',
        'Nursing Care', 'Oil', 'Online Media', 'Outsourcing', 'Package', 'Packaging', 'Paper',
        'Performing Arts', 'Pharmaceuticals', 'Philanthropy', 'Photography', 'Plastics', 'Political Organization',
        'Primary', 'Printing', 'Professional Training', 'Program Development', 'Public Policy', 'Public Relations',
        'Public Safety', 'Publishing', 'Railroad Manufacture', 'Ranching', 'Real Estate', 'Recreational Facilities',
        'Religious Institutions', 'Renewables', 'Research', 'Restaurants', 'Retail', 'Security',
        'Semiconductors', 'Shipbuilding', 'Sporting Goods', 'Sports', 'Staffing', 'Supermarkets',
        'Telecommunications', 'Textiles', 'Think Tanks', 'Tobacco', 'Translation', 'Transportation',
        'Utilities', 'Venture Capital', 'Veterinary', 'Warehousing', 'Wholesale', 'Wine',
        'Wireless', 'Writing', 'Technology', 'Healthcare', 'Finance', 'Education', 'Retail',
        'Manufacturing', 'Consulting', 'Non-profit', 'Government', 'Real Estate', 'Transportation',
        'Energy', 'Media', 'Telecommunications', 'Hospitality', 'Construction', 'Agriculture',
        'Automotive', 'Aerospace', 'Pharmaceuticals', 'Biotechnology', 'Entertainment', 'Sports',
        'Fashion', 'Food and Beverage', 'Legal', 'Architecture', 'Design', 'Marketing',
        'Human Resources', 'Sales', 'Customer Service', 'Operations', 'Supply Chain', 'Logistics',
        'Research and Development', 'Quality Assurance', 'Information Technology', 'Cybersecurity',
        'Data Science', 'Artificial Intelligence', 'Machine Learning', 'Software Development',
        'Web Development', 'Mobile Development', 'Cloud Computing', 'DevOps', 'Database Administration',
        'Network Administration', 'System Administration', 'Technical Support', 'Product Management',
        'Project Management', 'Business Analysis', 'Financial Analysis', 'Investment Banking',
        'Private Equity', 'Venture Capital', 'Insurance', 'Banking', 'Credit', 'Accounting',
        'Auditing', 'Tax', 'Risk Management', 'Compliance', 'Regulatory Affairs', 'Public Policy',
        'International Relations', 'Diplomacy', 'Trade', 'Import/Export', 'Customs', 'Freight',
        'Shipping', 'Warehousing', 'Distribution', 'Procurement', 'Sourcing', 'Vendor Management',
        'Contract Management', 'Business Development', 'Strategic Planning', 'Mergers and Acquisitions',
        'Corporate Development', 'Investor Relations', 'Public Relations', 'Communications',
        'Content Creation', 'Social Media', 'Digital Marketing', 'SEO/SEM', 'Email Marketing',
        'Event Planning', 'Trade Shows', 'Conferences', 'Training and Development', 'Organizational Development',
        'Change Management', 'Leadership Development', 'Talent Acquisition', 'Recruitment', 'Staffing',
        'Employee Relations', 'Benefits Administration', 'Payroll', 'HRIS', 'Workplace Safety',
        'Environmental Health and Safety', 'Sustainability', 'Corporate Social Responsibility', 'Diversity and Inclusion',
        'Ethics and Compliance', 'Internal Audit', 'External Audit', 'Forensic Accounting', 'Fraud Investigation',
        'Security', 'Physical Security', 'Information Security', 'Privacy', 'Data Protection',
        'Business Continuity', 'Disaster Recovery', 'Crisis Management', 'Emergency Management', 'Other'
    ]
    
    # Create enum type
    enum_values_str = "', '".join(industry_values)
    op.execute(f"CREATE TYPE industry AS ENUM ('{enum_values_str}')")
    
    # Convert string back to enum in user table
    op.execute('ALTER TABLE "user" ALTER COLUMN industry TYPE industry USING industry::industry')
    
    # Convert string back to enum in post table
    op.execute('ALTER TABLE "post" ALTER COLUMN industry TYPE industry USING industry::industry')
