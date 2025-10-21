import os
import json
import requests
from urllib.parse import urlparse
from dotenv import load_dotenv

def ensure_slug_column():
    """Ensure the blog_posts table has a slug column"""
    # Load environment variables from .env file in the parent directory
    env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
    load_dotenv(env_path)
    
    try:
        # Get database URL and auth token from environment variables
        db_url = os.getenv('TURSO_DATABASE_URL')
        auth_token = os.getenv('TURSO_AUTH_TOKEN')
        
        if not db_url or not auth_token:
            print("Error: Please set TURSO_DATABASE_URL and TURSO_AUTH_TOKEN environment variables")
            return False
            
        # Convert libsql:// URL to https:// for API calls
        if db_url.startswith('libsql://'):
            db_url = f"https://{db_url[9:]}"
        
        pipeline_url = f"{db_url}/v2/pipeline"
        
        headers = {
            'Authorization': f"Bearer {auth_token}",
            'Content-Type': 'application/json',
            'User-Agent': 'Turso-Slug-Column-Update/1.0'
        }
        
        # First, ensure the table exists
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS blog_posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            slug TEXT UNIQUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """.strip()
        
        create_payload = {
            'requests': [
                {'type': 'execute', 'stmt': {'sql': create_table_sql}},
                {'type': 'close'}
            ]
        }
        
        print(f"Connecting to database at: {db_url}")
        print("Checking database...")
        
        check_response = requests.post(
            pipeline_url,
            headers=headers,
            json=create_payload,
            timeout=30
        )
        
        if check_response.status_code != 200:
            print(f"Error checking database: {check_response.status_code} - {check_response.text}")
            return False
            
        response_data = check_response.json()
        
        # Check if table exists
        table_exists = len(response_data['results'][0]['response']['result']['rows']) > 0
        if not table_exists:
            print("ℹ️ 'blog_posts' table not found, creating it...")
            create_table_sql = """
            CREATE TABLE IF NOT EXISTS blog_posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                slug TEXT UNIQUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """.strip()
            
            create_payload = {
                'requests': [
                    {'type': 'execute', 'stmt': {'sql': create_table_sql}},
                    {'type': 'close'}
                ]
            }
            
            create_response = requests.post(
                pipeline_url,
                headers=headers,
                json=create_payload,
                timeout=30
            )
            
            if create_response.status_code != 200:
                print(f"❌ Failed to create blog_posts table: {create_response.status_code} - {create_response.text}")
                return False
                
            print("✅ Successfully created 'blog_posts' table with 'slug' column")
            return True
            
        # If table exists, check if slug column exists
        columns = [col[1] for col in response_data['results'][1]['response']['result']['rows']]
        if 'slug' in columns:
            print("✅ 'slug' column already exists in blog_posts table")
            return True
            
        print("ℹ️ 'slug' column not found in blog_posts table. Adding it now...")
        # Call add_slug_column directly
        return add_slug_column()
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return False

def add_slug_column():
    try:
        # Get database URL and auth token from environment variables
        db_url = os.getenv('TURSO_DATABASE_URL')
        auth_token = os.getenv('TURSO_AUTH_TOKEN')
        
        if not db_url or not auth_token:
            print("Error: Please set TURSO_DATABASE_URL and TURSO_AUTH_TOKEN environment variables")
            return False
            
        # Convert libsql:// URL to https:// for API calls
        if db_url.startswith('libsql://'):
            db_url = f"https://{db_url[9:]}"
        
        pipeline_url = f"{db_url}/v2/pipeline"
        
        headers = {
            'Authorization': f"Bearer {auth_token}",
            'Content-Type': 'application/json',
            'User-Agent': 'Turso-Slug-Column-Update/1.0'
        }
        
        # Check if slug column exists
        check_sql = "PRAGMA table_info(blog_posts);"
        
        check_payload = {
            'requests': [
                {'type': 'execute', 'stmt': {'sql': check_sql}},
                {'type': 'close'}
            ]
        }
        
        check_response = requests.post(
            pipeline_url,
            headers=headers,
            json=check_payload,
            timeout=30
        )
        
        if check_response.status_code != 200:
            print(f"Error checking database: {check_response.status_code} - {check_response.text}")
            return False
            
        response_data = check_response.json()
        columns = [col[1] for col in response_data['results'][0]['response']['result']['rows']]
        
        if 'slug' in columns:
            print("✅ 'slug' column already exists in blog_posts table")
            return True
            
        # Add slug column
        print("ℹ️ Adding 'slug' column to blog_posts table...")
        alter_sql = "ALTER TABLE blog_posts ADD COLUMN slug TEXT UNIQUE;"
        
        alter_payload = {
            'requests': [
                {'type': 'execute', 'stmt': {'sql': alter_sql}},
                {'type': 'close'}
            ]
        }
        
        alter_response = requests.post(
            pipeline_url,
            headers=headers,
            json=alter_payload,
            timeout=30
        )
        
        if alter_response.status_code != 200:
            print(f"❌ Failed to add 'slug' column: {alter_response.status_code} - {alter_response.text}")
            return False
            
        print("✅ Successfully added 'slug' column to blog_posts table")
        return True
        
    except Exception as e:
        print(f"❌ An error occurred: {str(e)}")
        return False

def main():
    # First ensure the table exists
    if ensure_slug_column():
        # Then ensure the slug column exists
        add_slug_column()

if __name__ == "__main__":
    main()
