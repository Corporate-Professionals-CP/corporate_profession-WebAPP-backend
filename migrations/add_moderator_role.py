"""Migration script to add is_moderator field to user table"""

import os
import sqlite3
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def migrate():
    """Add is_moderator column to user table if it doesn't exist"""
    # Create a local SQLite database for testing
    db_path = "test_database.db"
    
    # Connect to SQLite database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create user table if it doesn't exist (for testing purposes)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS "user" (
        id TEXT PRIMARY KEY,
        email TEXT UNIQUE NOT NULL,
        hashed_password TEXT NOT NULL,
        full_name TEXT,
        is_active BOOLEAN DEFAULT TRUE,
        is_admin BOOLEAN DEFAULT FALSE
    )
    """)
    
    # Check if column exists
    cursor.execute("PRAGMA table_info(user)")
    columns = cursor.fetchall()
    column_exists = any(column[1] == 'is_moderator' for column in columns)
    
    if not column_exists:
        print("Adding is_moderator column to user table...")
        cursor.execute('ALTER TABLE "user" ADD COLUMN is_moderator BOOLEAN NOT NULL DEFAULT FALSE')
        conn.commit()
        print("Migration completed successfully.")
    else:
        print("Column is_moderator already exists. No migration needed.")
    
    # Close connection
    conn.close()
    print(f"Local SQLite database created at {db_path}")

if __name__ == "__main__":
    migrate()