import json
import os
import sys
from pathlib import Path

# Add the project root to the Python path
sys.path.append(str(Path(__file__).parent.parent.parent))

try:
    # Try to import your existing script
    from SCRAP.keyword_searcher import process_keyword, SERPSearcher
    IMPORT_SUCCESS = True
except ImportError as e:
    IMPORT_SUCCESS = False
    print(f"Failed to import SCRAP.keyword_searcher: {e}", file=sys.stderr)

def handler(event, context):
    try:
        # Parse the request
        http_method = event.get('httpMethod', '').upper()
        
        if http_method != 'POST':
            return {
                'statusCode': 405,
                'body': json.dumps({'error': 'Method not allowed'}),
                'headers': {'Content-Type': 'application/json'}
            }
        
        # Parse request body
        body = event.get('body', '{}')
        if isinstance(body, str):
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                return {
                    'statusCode': 400,
                    'body': json.dumps({'error': 'Invalid JSON'}),
                    'headers': {'Content-Type': 'application/json'}
                }
        else:
            data = body
        
        keyword = data.get('keyword')
        if not keyword:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'Keyword is required'}),
                'headers': {'Content-Type': 'application/json'}
            }
        
        # Check if imports were successful
        if not IMPORT_SUCCESS:
            return {
                'statusCode': 500,
                'body': json.dumps({'error': 'Failed to import required modules'}),
                'headers': {'Content-Type': 'application/json'}
            }
        
        # Initialize searcher with environment variables
        serpapi_key = os.getenv('SERPAPI_KEY')
        if not serpapi_key:
            return {
                'statusCode': 500,
                'body': json.dumps({'error': 'SERPAPI_KEY environment variable not set'}),
                'headers': {'Content-Type': 'application/json'}
            }
            
        searcher = SERPSearcher(api_key=serpapi_key)
        
        # Process the keyword
        result = process_keyword(keyword, searcher)
        
        # Convert result to JSON-serializable format
        if hasattr(result, '__dict__'):
            result = result.__dict__
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'status': 'success',
                'data': result
            }),
            'headers': {'Content-Type': 'application/json'}
        }
        
    except Exception as e:
        import traceback
        error_details = {
            'error': str(e),
            'type': type(e).__name__,
            'traceback': traceback.format_exc()
        }
        print(f"Error in handler: {error_details}", file=sys.stderr)
        
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': 'Internal server error',
                'details': str(e)
            }),
            'headers': {'Content-Type': 'application/json'}
        }

# For local testing
if __name__ == "__main__":
    test_event = {
        'httpMethod': 'POST',
        'body': json.dumps({'keyword': 'test'}),
        'headers': {}
    }
    
    # Set up environment for local testing
    os.environ['SERPAPI_KEY'] = 'your_test_key_here'
    
    # Run the handler
    response = handler(test_event, None)
    print(json.dumps(response, indent=2))
