import os
import json
import requests
from dotenv import load_dotenv
from pathlib import Path

def list_blog_posts():
    """List all blog posts and their slugs"""
    # Load environment variables from SCRAP/.env
    env_path = Path(__file__).parent / 'SCRAP' / '.env'
    load_dotenv(env_path)
    
    turso_url = os.getenv("TURSO_DATABASE_URL")
    turso_auth_token = os.getenv("TURSO_AUTH_TOKEN")
    
    if not turso_url or not turso_auth_token:
        print("Error: Missing Turso credentials in .env file")
        print(f"TURSO_DATABASE_URL: {'Set' if turso_url else 'Not set'}")
        print(f"TURSO_AUTH_TOKEN: {'Set' if turso_auth_token else 'Not set'}")
        print(f"Looking for .env at: {env_path.absolute()}")
        return
    
    # Build the URL
    base_url = f"https://{turso_url}" if not turso_url.startswith(('http://', 'https://')) else turso_url
    pipeline_url = f"{base_url}/v2/pipeline"
    
    headers = {
        'Authorization': f'Bearer {turso_auth_token}',
        'Content-Type': 'application/json'
    }
    
    # SQL to check if slug column exists
    check_columns_sql = """
    SELECT name FROM pragma_table_info('blog_posts') WHERE name = 'slug';
    """.strip()
    
    # SQL to get all posts
    select_sql = """
    SELECT title, slug, substr(content, 1, 100) || '...' as preview 
    FROM blog_posts 
    ORDER BY rowid DESC;
    """.strip()
    
    try:
        # First check if slug column exists
        check_payload = {
            'requests': [
                {
                    'type': 'execute',
                    'stmt': {'sql': check_columns_sql}
                },
                {'type': 'close'}
            ]
        }
        
        response = requests.post(
            pipeline_url,
            headers=headers,
            data=json.dumps(check_payload),
            timeout=30
        )
        
        has_slug = bool(response.json().get('results', [{}])[0].get('response', {}).get('result', {}).get('rows'))
        
        # First, check if the table exists
        check_table_sql = """
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name='blog_posts';
        """.strip()
        
        # Create payload to check table existence
        table_check_payload = {
            'requests': [
                {
                    'type': 'execute',
                    'stmt': {'sql': check_table_sql}
                },
                {'type': 'close'}
            ]
        }
        
        # Send table check request
        table_check_response = requests.post(
            pipeline_url,
            headers=headers,
            data=json.dumps(table_check_payload),
            timeout=30
        )
        
        table_check_result = table_check_response.json()
        table_exists = bool(table_check_result.get('results', [{}])[0].get('response', {}).get('result', {}).get('rows', []))
        
        if not table_exists:
            print("The 'blog_posts' table does not exist in the database.")
            return
            
        # Get all posts
        payload = {
            'requests': [
                {
                    'type': 'execute',
                    'stmt': {'sql': select_sql}
                },
                {'type': 'close'}
            ]
        }
        
        response = requests.post(
            pipeline_url,
            headers=headers,
            data=json.dumps(payload),
            timeout=30
        )
        
        if response.status_code != 200:
            print(f"Error: Received status code {response.status_code} from database")
            print(f"Response: {response.text}")
            return
            
        result = response.json()
        print("\n=== Debug: Raw Database Response ===")
        print(json.dumps(result, indent=2))
        print("=" * 50 + "\n")
        
        rows = result.get('results', [{}])[0].get('response', {}).get('result', {}).get('rows', [])
        
        if not rows:
            print("No blog posts found in the 'blog_posts' table.")
            return
            
        print("\n📝 Blog Posts\n" + "="*50)
        for row in rows:
            # Extract values from the database response objects
            title = row[0].get('value') if isinstance(row[0], dict) else row[0]
            slug = (row[1].get('value') if isinstance(row[1], dict) else row[1]) if has_slug and len(row) > 1 else "[No slug]"
            preview = (row[2].get('value') if isinstance(row[2], dict) else row[2]) if len(row) > 2 else ""
            
            # Format and print the post information
            print(f"\n📌 Title: {title}")
            print(f"🔗 Slug: {slug}")
            if preview:
                # Keep markdown formatting in the preview
                preview = preview.strip()
                # Limit preview to first 2 lines or 150 characters
                preview_lines = preview.split('\n')[:2]
                preview = '\n'.join(preview_lines)
                if len(preview) > 150:
                    preview = preview[:147] + '...'
                print(f"\n📄 Preview:\n{preview}")
            print("\n" + "─" * 50)
            
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    list_blog_posts()
