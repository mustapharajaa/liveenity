import os
import requests
import json
import sys
import subprocess
import time
import random
from typing import List, Dict, Optional, Any
from dotenv import load_dotenv

# --- FINAL CORRECTED CONSTANT DEFINITIONS ---
# SCRIPT_DIR is where keyword_searcher.py is located (e.g., C:\...\liveenity\SCRAP)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# ***FIXED: SCRAP_DIR is set to the script's directory (SCRIPT_DIR)***
# This targets C:\Users\rajam\Desktop\liveenity\SCRAP
SCRAP_DIR = SCRIPT_DIR 

# ==============================================================================
# PLACEHOLDER FUNCTIONS (Assumed to be in your original script)
# ==============================================================================

def load_keywords(filepath: str) -> List[str]:
    """Loads keywords from KEYWORDS.txt."""
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            return [line.strip() for line in f if line.strip()]
    return []

class SERPSearcher:
    """SERP API Searcher using SerpAPI."""
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://serpapi.com/search"
    
    def search_keyword(self, keyword: str) -> Optional[Dict[str, Any]]:
        """Search for a keyword using SerpAPI.
        
        Args:
            keyword: The search query string
            
        Returns:
            Dict containing search results or None if there was an error
        """
        try:
            params = {
                'q': keyword,
                'api_key': self.api_key,
                'num': 10,  # Get up to 10 results
                'hl': 'en',  # Language: English
                'gl': 'us',  # Country: United States
                'google_domain': 'google.com'
            }
            
            response = requests.get(self.base_url, params=params, timeout=30)
            response.raise_for_status()  # Raise an exception for HTTP errors
            
            data = response.json()
            
            # Extract organic results
            results = {
                'search_metadata': {
                    'status': 'Success',
                    'total_results': data.get('search_information', {}).get('total_results', 0),
                    'query': data.get('search_parameters', {}).get('q', '')
                },
                'organic_results': []
            }
            
            # Format the results to match the expected structure
            for result in data.get('organic_results', []):
                results['organic_results'].append({
                    'title': result.get('title'),
                    'link': result.get('link'),
                    'snippet': result.get('snippet')
                })
                
            return results
            
        except requests.exceptions.RequestException as e:
            print(f"Error searching for '{keyword}': {e}")
            if hasattr(e, 'response') and e.response:
                print(f"Status code: {e.response.status_code}")
                print(f"Response: {e.response.text[:200]}...")
            return None
        except Exception as e:
            print(f"Unexpected error: {e}")
            return None

def extract_top_links(results: Dict[str, Any], count: int) -> List[str]:
    """Extracts the top N links from the search results."""
    return [r['link'] for r in results.get('organic_results', [])][:count]

def scrape_website(url: str) -> Optional[str]:
    """Scrape website content using ScrapingDog API."""
    try:
        # Get API key from environment variables
        api_key = os.getenv('SCRAPINGDOG_API_KEY')
        if not api_key:
            print("⚠️  SCRAPINGDOG_API_KEY not found in environment variables")
            return None
            
        print(f"  - Scraping: {url}")
        
        # Prepare the ScrapingDog API request
        params = {
            'api_key': api_key,
            'url': url,
            'dynamic': 'true',  # Enable JavaScript rendering
            'render_js': 'true',
            'wait': '3000',  # Wait 3 seconds for JS to load
            'timeout': '30000'  # 30 second timeout
        }
        
        # Make the request to ScrapingDog API
        response = requests.get(
            'https://api.scrapingdog.com/scrape',
            params=params,
            timeout=45  # Increased timeout for the request
        )
        
        # Check if the request was successful
        response.raise_for_status()
        
        # Return the scraped content
        return response.text
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Error scraping {url}: {e}")
        if hasattr(e, 'response') and e.response:
            print(f"  Status code: {e.response.status_code}")
            print(f"  Response: {e.response.text[:200]}...")
        return None
    except Exception as e:
        print(f"❌ Unexpected error while scraping {url}: {e}")
        return None

# ==============================================================================
# MAIN SCRIPT LOGIC
# ==============================================================================

def cleanup_files(keyword: str) -> None:
    """Clean up search results, scraped files, and update KEYWORDS.txt"""
    try:
        # Remove search results JSON file (in SCRAP_DIR)
        json_file = f"{keyword}_results.json"
        json_file_path = os.path.join(SCRAP_DIR, json_file) 
        if os.path.exists(json_file_path):
            os.remove(json_file_path)
            print(f"Removed search results: {json_file}")
        
        # Remove scraped HTML files (in SCRAP_DIR)
        for i in range(1, 3):  # Remove link_1.html and link_2.html
            html_file_name = f"scraped_{keyword}_link_{i}.html"
            html_file_path = os.path.join(SCRAP_DIR, html_file_name) 
            
            if os.path.exists(html_file_path):
                os.remove(html_file_path)
                print(f"Removed scraped file: {html_file_path}")
                
        # Remove the processed keyword from KEYWORDS.txt
        keywords_file = os.path.join(SCRAP_DIR, 'KEYWORDS.txt')
        
        if os.path.exists(keywords_file):
             with open(keywords_file, 'r', encoding='utf-8') as f:
                 lines = f.readlines()
             
             keyword_with_spaces = keyword.replace('_', ' ').strip()
             
             updated_lines = [line.strip() for line in lines 
                              if line.strip().upper() not in [keyword.upper(), keyword_with_spaces.upper()] 
                              and line.strip()]
             
             with open(keywords_file, 'w', encoding='utf-8') as f:
                 f.write('\n'.join(updated_lines))
                 if updated_lines:
                     f.write('\n')
             
             print(f"Removed processed keyword '{keyword}' from KEYWORDS.txt")

    except Exception as e:
        print(f"Error during cleanup: {e}")

def run_blog_generation(keyword: str) -> bool:
    """Run the blog post generation script and save to Turso"""
    try:
        print("\nGenerating blog post...")
        
        load_dotenv()
        
        required_vars = ['TURSO_DATABASE_URL', 'TURSO_AUTH_TOKEN', 'GEMINI_API_KEY']
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        
        if missing_vars:
            print(f"❌ Missing required environment variables: {', '.join(missing_vars)}")
            print("Please add them to your .env file")
            return False
        
        # --- PASS CORRECTED PATH TO EXTERNAL SCRIPT ---
        # The external script (generate_blog.py) now receives the correct full path.
        script_args = [sys.executable, 'generate_blog.py', keyword, SCRAP_DIR]
        
        # Run the blog generation with the keyword and the scrap directory path as arguments
        result = subprocess.run(
            script_args,
            cwd=SCRAP_DIR, # Run from the script's directory (C:\...\SCRAP)
            capture_output=True,
            text=True,
            env=os.environ
        )
        
        if result.stdout:
             print(result.stdout)
        if result.stderr:
             print("Error:", result.stderr)
         
        success = result.returncode == 0
         
        if success:
             # Check for a successful save message
             if "Successfully saved to Turso database" in result.stdout:
                 print("✅ Blog post saved to Turso database")
             else:
                 # If subprocess succeeds but doesn't confirm DB save
                 print("⚠️  Blog post generated but may not have been saved to Turso")
                 print("    Check generate_blog.py output and environment variables.")
             
             cleanup_files(keyword)
        else:
             print("❌ Failed to generate blog post")
             
        return success
    except Exception as e:
        print(f"❌ Error generating blog post: {e}")
        return False

def process_keyword(keyword: str, searcher: SERPSearcher):
    """Process a single keyword through the entire pipeline."""
    keyword_clean = keyword.strip()
    if not keyword_clean:
        return False
        
    keyword_clean_upper = keyword_clean.replace(' ', '_').upper()
    print(f"\n🔍 Processing keyword: {keyword_clean}")
    
    # Search and save results
    results = searcher.search_keyword(keyword_clean)
    
    if not results:
        print(f"No results found for '{keyword_clean}'")
        return False
        
    print(f"Found {len(results.get('organic_results', []))} results")
    
    # Save search results JSON
    results_file = f"{keyword_clean_upper}_results.json"
    results_file_path = os.path.join(SCRAP_DIR, results_file)
    with open(results_file_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2)
    print(f"Saved search results to {results_file_path}")
    
    top_links = extract_top_links(results, count=2)
    if not top_links:
        print("No links found to scrape.")
        return False
        
    print("\nScraping top links:")
    for i, link in enumerate(top_links, 1):
        print(f"{i}. {link}")
        scrape_result = scrape_website(link)
        if scrape_result:
            filename = f"scraped_{keyword_clean_upper}_link_{i}.html"
            file_path = os.path.join(SCRAP_DIR, filename) 
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(scrape_result)
            print(f"  - Saved to {file_path}")
    
    # Generate the blog post
    return run_blog_generation(keyword_clean_upper)

def main():
    # Load environment variables
    env_loaded = False
    
    # Check for .env in the same directory as the script (SCRAP_DIR)
    env_path = os.path.join(SCRAP_DIR, '.env')
    if os.path.exists(env_path):
        load_dotenv(env_path)
        print(f"Loaded environment variables from {env_path}")
        env_loaded = True
    
    # Check for .env.local one level up (in C:\Users\rajam\Desktop\liveenity\)
    if not env_loaded:
        parent_dir = os.path.dirname(SCRAP_DIR)
        env_path = os.path.join(parent_dir, '.env.local')
        if os.path.exists(env_path):
            load_dotenv(env_path)
            print(f"Loaded environment variables from {env_path}")
            env_loaded = True
    
    if not env_loaded:
        print("⚠️  No .env or .env.local file found. Some features may not work.")
    
    # Get API key from environment variables
    API_KEY = os.getenv('SERP_API_KEY')
    
    if not API_KEY:
        print("Error: SERP_API_KEY not found in environment variables")
        print("Please add the following line to your .env file:")
        print("SERP_API_KEY=your_serp_api_key_here")
        return

    # Ensure directory exists
    try:
        os.makedirs(SCRAP_DIR, exist_ok=True)
        print(f"Target directory for scraping: {SCRAP_DIR}")
    except Exception as e:
        print(f"❌ Error ensuring directory {SCRAP_DIR} exists: {e}")
        return

    keywords_file = os.path.join(SCRAP_DIR, 'KEYWORDS.txt')
    searcher = SERPSearcher(API_KEY)
    processed_keywords = set()
    
    print("🚀 Starting keyword processing. Press Ctrl+C to stop.")
    print(f"Monitoring file: {keywords_file}")
    print("Add one keyword per line to process them automatically.")
    
    try:
        while True:
            # Read current keywords
            with open(keywords_file, 'r', encoding='utf-8') as f:
                current_keywords = [line.strip() for line in f if line.strip()]
            
            # Process new keywords
            for keyword in current_keywords:
                if keyword and keyword not in processed_keywords:
                    process_keyword(keyword, searcher)
                    processed_keywords.add(keyword)
                    
                    # Remove the processed keyword from the file
                    with open(keywords_file, 'w', encoding='utf-8') as f:
                        f.write('\n'.join(k for k in current_keywords if k != keyword))
                    
                    # Add delay after successful blog generation
                    delay_seconds = random.randint(60, 120)  # 1-2 minutes
                    print(f"⏳ Waiting {delay_seconds} seconds before next keyword...")
                    time.sleep(delay_seconds)
            
            # Short delay before checking for new keywords
            time.sleep(5)  # Check every 5 seconds
            
    except KeyboardInterrupt:
        print("\n👋 Script stopped by user.")
    except Exception as e:
        print(f"\n❌ An error occurred: {e}")
    finally:
        print("✅ Processing complete. Any remaining keywords are saved in the file.")


if __name__ == "__main__":
    main()