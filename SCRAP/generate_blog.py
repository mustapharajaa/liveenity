import os
import sys
import json
import requests
from typing import List, Dict, Optional, Tuple
import google.generativeai as genai
from dotenv import load_dotenv
from datetime import datetime

def load_search_results(json_file: str) -> Dict:
    """Load search results from JSON file"""
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading search results: {e}")
        return {}

def load_scraped_content(base_filename: str, count: int = 2) -> List[Dict]:
    """Load scraped content from HTML files"""
    contents = []
    for i in range(1, count + 1):
        try:
            filename = f"scraped_{base_filename}_link_{i}.html"
            with open(filename, 'r', encoding='utf-8') as f:
                contents.append({
                    'position': i,
                    'filename': filename,
                    'content': f.read()[:10000]  # Limit content length
                })
        except Exception as e:
            print(f"Error loading scraped content {i}: {e}")
    return contents

def list_available_models():
    """List all available models"""
    try:
        genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
        models = genai.list_models()
        print("\nAvailable models:")
        for model in models:
            print(f"- {model.name}")
        return [model.name for model in models]
    except Exception as e:
        print(f"Error listing models: {e}")
        return []

def generate_blog_post(search_results: Dict, scraped_contents: List[Dict]) -> str:
    """Generate blog post content using Gemini AI"""
    # Extract search query and top results
    query = search_results.get('search_parameters', {}).get('q', 'the topic')
    top_results = "\n".join(
        f"{i+1}. {res.get('title', '')} - {res.get('link', '')}"
        for i, res in enumerate(search_results.get('organic_results', [])[:5])
    )
    
    # Get current year
    from datetime import datetime
    current_year = datetime.now().year
    
    # Prepare the prompt
    prompt = f"""
    Create a comprehensive, SEO-optimized blog post about: {query}
    
    Important Instructions:
    - DO NOT include any introductory text like "Here is the comprehensive blog post..."
    -DO NOT include any introductory text like "**Meta Title:**"...
    - Start directly with the content
    - The title should include the current year ({current_year})
    - Content should be between 500-1300 words
    - Focus on providing up-to-date and accurate information for {current_year}
    
    Search Results Analysis:
    {top_results}
    
    Scraped Content (first 10k chars each):
    {json.dumps(scraped_contents, indent=2)}
    
    Required Structure:
    1. Start directly with the meta title and meta description (formatted as shown below)
    2. Then the H1 heading (title)
    3. Then the main content with H2 and H3 subheadings
    4. Include a conclusion and call-to-action
    
    Format Example:
    **Meta Title:** [Title Here]
    
    **Meta Description:** [Description Here]
    
    # [Main Title Here]
    
    [Content starts here...]
    
    Ensure the content is:
    - Well-structured with proper headings
    - Naturally includes relevant keywords
    - Provides valuable, up-to-date information
    - Has a professional, engaging tone
    - Is between 500-1300 words
    - Avoids any introductory text or meta-commentary
    """
    
    try:
        # Initialize Gemini with the specific model
        genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
        
        # Use the latest available model
        model = genai.GenerativeModel('gemini-2.5-pro')
        
        # Generate content with error handling
        response = model.generate_content(prompt)
        
        # Return the text content
        if hasattr(response, 'text'):
            return response.text
        elif hasattr(response, 'candidates') and response.candidates:
            return response.candidates[0].content.parts[0].text
        else:
            print("Unexpected response format from Gemini API")
            return ""
        
    except Exception as e:
        print(f"Error generating blog post: {e}")
        return ""

def load_environment() -> bool:
    """Load environment variables from .env file"""
    # Load from .env in current directory (same as test_turso.py)
    if load_dotenv():
        print("Loaded environment variables from .env")
        return True
    
    # If not found, try .env in parent directory
    parent_env = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
    if os.path.exists(parent_env):
        load_dotenv(parent_env)
        print(f"Loaded environment variables from {parent_env}")
        return True
    
    print("Warning: No .env file found")
    return False

def main():
    # Set console encoding to UTF-8 for Windows
    if sys.platform == 'win32':
        import io
        # Use the existing sys module instead of reimporting
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    
    # Load environment variables
    if not load_environment() or not os.getenv('GEMINI_API_KEY'):
        safe_print("Error: GEMINI_API_KEY not found in environment variables")
        print("Please add your Gemini API key to either:")
        print("1. .env file in the SCRAP directory")
        print("2. .env.local file in the parent directory")
        print("\nExample content:")
        print("GEMINI_API_KEY=your_api_key_here")
        return
    
    # Get keyword from command line arguments
    if len(sys.argv) < 2:
        print("Error: Please provide a keyword as a command line argument")
        print("Usage: python generate_blog.py KEYWORD")
        return
    
    keyword = sys.argv[1].upper().replace(' ', '_')
    print(f"Processing keyword: {keyword}")
    
    # File paths
    results_file = f"{keyword}_results.json"
    
    # Load data
    search_results = load_search_results(results_file)
    if not search_results:
        print("No search results found.")
        return
    
    scraped_contents = load_scraped_content(keyword)
    if not scraped_contents:
        print("No scraped content found.")
        return
    
    # Generate blog post
    print("Generating blog post...")
    blog_content = generate_blog_post(search_results, scraped_contents)
    
    # Save the blog post to a file
    output_file = f"blog_post_{keyword}.md"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(blog_content)
    
    # Extract title and content for the API
    title, content = parse_blog_content(blog_content)
    
    # Save to database via API
    if save_to_database(keyword, title, content, blog_content):
        safe_print("[SUCCESS] Blog post generated and saved to database successfully!")
    else:
        safe_print(f"[WARNING] Blog post generated and saved to {output_file}, but failed to save to database")

def parse_blog_content(blog_content: str) -> Tuple[str, str]:
    """
    Extract title and content from blog post.
    The title is taken from the first line that starts with '**Meta Title:**'.
    If not found, falls back to the first H1 heading.
    """
    lines = blog_content.split('\n')
    title = ""
    content_start = 0
    
    # First try to find the meta title (handle both with and without space after colon)
    for i, line in enumerate(lines):
        line = line.strip()
        if line.startswith('**Meta Title:**'):
            # Remove '**Meta Title:**' and any leading/trailing whitespace
            title = line.replace('**Meta Title:**', '').strip()
            content_start = i + 1
            break
    
    # If no meta title found, look for the first H1 heading
    if not title:
        for i, line in enumerate(lines):
            line = line.strip()
            if line.startswith('# '):
                title = line[2:].strip()  # Remove the '# ' prefix
                content_start = i + 1
                break
    
    # The rest is content
    content = '\n'.join(lines[content_start:]).strip()
    
    return title, content

def safe_print(*args, **kwargs):
    """Helper function to safely print Unicode characters in Windows"""
    try:
        print(*args, **kwargs)
    except UnicodeEncodeError:
        # If Unicode fails, replace unsupported characters
        text = ' '.join(str(arg) for arg in args)
        print(text.encode('ascii', 'replace').decode('ascii'), **kwargs)

def generate_slug(title: str) -> str:
    """Generate a URL-friendly slug from the title"""
    import re
    from unidecode import unidecode
    
    # Convert to ASCII
    slug = unidecode(title)
    # Convert to lowercase
    slug = slug.lower()
    # Remove special characters
    slug = re.sub(r'[^\w\s-]', '', slug)
    # Replace spaces with hyphens
    slug = re.sub(r'[\s-]+', '-', slug)
    # Remove leading/trailing hyphens
    slug = slug.strip('-_')
    return slug

def update_sitemap(slug: str) -> bool:
    """Update sitemap.xml with new blog post URL"""
    try:
        sitemap_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'sitemap.xml')
        today = datetime.now().strftime('%Y-%m-%d')
        
        # Create sitemap if it doesn't exist
        if not os.path.exists(sitemap_path):
            with open(sitemap_path, 'w', encoding='utf-8') as f:
                f.write('''<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <url>
        <loc>https://yourdomain.com/</loc>
        <lastmod>''' + today + '''</lastmod>
        <changefreq>daily</changefreq>
        <priority>1.0</priority>
    </url>
</urlset>''')
        
        # Read current sitemap
        with open(sitemap_path, 'r', encoding='utf-8') as f:
            sitemap = f.read()
        
        # Add new URL before closing urlset
        new_url = f'''
    <url>
        <loc>https://yourdomain.com/pages/{slug}</loc>
        <lastmod>{today}</lastmod>
        <changefreq>weekly</changefreq>
        <priority>0.8</priority>
    </url>
</urlset>'''
        
        updated_sitemap = sitemap.replace('</urlset>', new_url)
        
        # Write updated sitemap
        with open(sitemap_path, 'w', encoding='utf-8') as f:
            f.write(updated_sitemap)
            
        safe_print(f"[+] Updated sitemap with new URL: /pages/{slug}")
        return True
        
    except Exception as e:
        safe_print(f"[!] Error updating sitemap: {str(e)}")
        return False

def save_to_database(keyword: str, title: str, content: str, full_content: str) -> bool:
    """Save blog post to Turso database with title, content, and slug"""
    try:
        safe_print("\n=== Starting database save process ===")
        
        # Get Turso credentials from environment variables
        turso_url = os.getenv('TURSO_DATABASE_URL')
        turso_auth_token = os.getenv('TURSO_AUTH_TOKEN')
        
        safe_print(f"Using Turso URL: {turso_url}")
        safe_print(f"Auth token: {'*' * 20}{turso_auth_token[-4:] if turso_auth_token else 'None'}")
        
        if not turso_url or not turso_auth_token:
            safe_print("[X] Error: Missing Turso credentials")
            if not turso_url:
                safe_print("- TURSO_DATABASE_URL is not set")
            if not turso_auth_token:
                safe_print("- TURSO_AUTH_TOKEN is not set")
            return False
        
        safe_print(f"Using title: {title}")
        # Generate a proper URL-friendly slug
        slug = generate_slug(title)
        safe_print(f"Generated slug: {slug}")
        
        # Prepare the base URL and headers
        base_url = f"https://{turso_url}" if not turso_url.startswith(('http://', 'https://')) else turso_url
        pipeline_url = f"{base_url}/v2/pipeline"
        headers = {
            'Authorization': f'Bearer {turso_auth_token}',
            'Content-Type': 'application/json'
        }
        
        # Prepare the insert query with REPLACE to handle duplicates
        insert_sql = """
        INSERT OR REPLACE INTO blog_posts (title, content, slug)
        VALUES (?, ?, ?)
        """.strip()
        
        # Create the payload with proper parameter binding
        payload = {
            'requests': [
                {
                    'type': 'execute',
                    'stmt': {
                        'sql': insert_sql,
                        'args': [
                            {'type': 'text', 'value': title},
                            {'type': 'text', 'value': full_content},
                            {'type': 'text', 'value': slug}
                        ]
                    }
                },
                {'type': 'close'}
            ]
        }
        
        safe_print("\nSending request to Turso...")
        safe_print(f"URL: {pipeline_url}")
        safe_print(f"SQL: {insert_sql}")
        
        # Send the request to Turso's REST API
        try:
            response = requests.post(
                pipeline_url,
                headers=headers,
                data=json.dumps(payload),
                timeout=30
            )
            
            safe_print("\n=== Response from Turso ===")
            safe_print(f"Status Code: {response.status_code}")
            safe_print(f"Response Text: {response.text}")
            
            if response.status_code == 200:
                safe_print("[+] Successfully saved to Turso database!")
                # Update sitemap after successful save
                update_sitemap(slug)
                return True
            else:
                safe_print("[X] Failed to save to Turso database")
                if response.status_code == 401:
                    safe_print("Authentication failed. Please check your TURSO_AUTH_TOKEN")
                elif response.status_code == 404:
                    safe_print("Endpoint not found. Please check your TURSO_DATABASE_URL")
                return False
                
        except requests.exceptions.RequestException as e:
            safe_print(f"\n[X] Network error: {str(e)}")
            return False
            
    except Exception as e:
        safe_print(f"\n[X] Error saving to Turso database: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    main()
