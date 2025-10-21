import os
import json
import requests
import sys
from dotenv import load_dotenv
from pathlib import Path

def get_blog_post(slug):
    """Fetch a single blog post by its slug"""
    # Load environment variables
    env_path = Path(__file__).parent / 'SCRAP' / '.env'
    load_dotenv(env_path)
    
    turso_url = os.getenv("TURSO_DATABASE_URL")
    turso_auth_token = os.getenv("TURSO_AUTH_TOKEN")
    
    if not turso_url or not turso_auth_token or not slug:
        print("Error: Missing required parameters or environment variables")
        print(f"TURSO_DATABASE_URL: {'Set' if turso_url else 'Not set'}")
        print(f"TURSO_AUTH_TOKEN: {'Set' if turso_auth_token else 'Not set'}")
        print(f"Slug: {slug if slug else 'Not provided'}")
        return None
    
    # Build the URL
    base_url = f"https://{turso_url}" if not turso_url.startswith(('http://', 'https://')) else turso_url
    pipeline_url = f"{base_url.rstrip('/')}/v2/pipeline"
    
    headers = {
        'Authorization': f'Bearer {turso_auth_token}',
        'Content-Type': 'application/json'
    }
    
    # SQL to get a single post by slug
    select_sql = """
    SELECT title, slug, content
    FROM blog_posts 
    WHERE slug = ? 
    LIMIT 1;
    """.strip()
    
    try:
        # Create payload with parameterized query
        payload = {
            'requests': [
                {
                    'type': 'execute',
                    'stmt': {
                        'sql': select_sql,
                        'args': [{'type': 'text', 'value': slug}]
                    }
                },
                {'type': 'close'}
            ]
        }
        
        # Make the request
        response = requests.post(
            pipeline_url,
            headers=headers,
            json=payload,
            timeout=30
        )
        
        if response.status_code != 200:
            print(f"Error: Received status code {response.status_code} from database")
            print(f"Response: {response.text}")
            return None
            
        result = response.json()
        rows = result.get('results', [{}])[0].get('response', {}).get('result', {}).get('rows', [])
        
        if not rows:
            print(f"No blog post found with slug: {slug}")
            return None
            
        # Extract column names from the result
        columns = [col['name'] for col in result['results'][0]['response']['result']['cols']]
        
        # Convert the first row to a dictionary using column names
        row = rows[0]
        post = {}
        
        for idx, col_name in enumerate(columns):
            if idx < len(row):
                post[col_name] = row[idx].get('value') if isinstance(row[idx], dict) else row[idx]
                
        # For backward compatibility, ensure these keys exist
        post['title'] = post.get('title', 'No Title')
        post['content'] = post.get('content', 'No content available')
        post['slug'] = post.get('slug', '')
        
        return post
        
    except Exception as e:
        print(f"Error fetching blog post: {str(e)}")
        return None

def main():
    if len(sys.argv) != 2:
        print("Usage: python get_post.py <slug>")
        print("Example: python get_post.py my-awesome-blog-post")
        sys.exit(1)
        
    slug = sys.argv[1]
    post = get_blog_post(slug)
    
    if post:
        print("\n" + "📝 BLOG POST".center(60, '='))
        print(f"\nTITLE: {post['title']}")
        print("-" * 80)
        print(f"SLUG:  {post['slug']}")
        if post.get('created_at'):
            print(f"DATE:  {post['created_at']}")
        print("\n" + " CONTENT ".center(80, '='))
        print(post['content'])
        print("=" * 80)
    else:
        print(f"\n❌ No blog post found with slug: {slug}")
        print("\nTry listing all posts with: python list_posts.py")

if __name__ == "__main__":
    main()
