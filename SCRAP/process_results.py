import json
import os
from typing import List
from keyword_searcher import scrape_website

def extract_links_from_json(json_file: str, max_links: int = 2) -> List[str]:
    """Extract top N links from the search results JSON file"""
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        links = []
        if 'organic_results' in data:
            for result in data['organic_results'][:max_links]:
                if 'link' in result:
                    links.append(result['link'])
        return links
    except Exception as e:
        print(f"Error processing JSON file: {e}")
        return []

def main():
    # Path to the results JSON file
    results_file = os.path.join(os.path.dirname(__file__), 'BUY_YOUTUBE_SUBSCRIBERS_results.json')
    
    # Extract links from the JSON file
    links = extract_links_from_json(results_file, max_links=2)
    
    if not links:
        print("No links found in the results file.")
        return
    
    print(f"Found {len(links)} links to process:")
    
    # Scrape each link
    for i, link in enumerate(links, 1):
        print(f"\nScraping link {i}: {link}")
        html_content = scrape_website(link)
        
        if html_content:
            # Save the scraped content
            filename = f"scraped_link_{i}.html"
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(html_content)
            print(f"  - Saved to {filename}")
        else:
            print(f"  - Failed to scrape {link}")

if __name__ == "__main__":
    main()
