import os
import requests
from dotenv import load_dotenv

def setup_blog_table():
    """Set up the blog_posts table with the correct structure"""
    # Load environment variables
    env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
    load_dotenv(env_path)
    
    db_url = os.getenv('TURSO_DATABASE_URL')
    auth_token = os.getenv('TURSO_AUTH_TOKEN')
    
    if not db_url or not auth_token:
        print("❌ Error: Missing TURSO_DATABASE_URL or TURSO_AUTH_TOKEN")
        return False
    
    # Convert libsql:// URL to https://
    if db_url.startswith('libsql://'):
        db_url = f"https://{db_url[9:]}"
    
    pipeline_url = f"{db_url}/v2/pipeline"
    headers = {
        'Authorization': f"Bearer {auth_token}",
        'Content-Type': 'application/json'
    }
    
    # SQL to create the table with the exact structure you want
    create_sql = """
    CREATE TABLE IF NOT EXISTS blog_posts (
        title TEXT NOT NULL,
        content TEXT NOT NULL,
        slug TEXT UNIQUE
    );
    """
    
    payload = {
        'requests': [
            {'type': 'execute', 'stmt': {'sql': create_sql}},
            {'type': 'close'}
        ]
    }
    
    try:
        print(f"Connecting to database at: {db_url}")
        print("Setting up blog_posts table...")
        
        response = requests.post(
            pipeline_url,
            headers=headers,
            json=payload,
            timeout=30
        )
        
        if response.status_code == 200:
            print("✅ Successfully set up blog_posts table")
            return True
        else:
            print(f"❌ Failed to set up table: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ An error occurred: {str(e)}")
        return False

if __name__ == "__main__":
    setup_blog_table()
