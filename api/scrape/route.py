from http.server import BaseHTTPRequestHandler
import json
import os
import sys
from pathlib import Path

# Add the project root to the Python path
sys.path.append(str(Path(__file__).parent.parent.parent))

# Import your existing script
from SCRAP.keyword_searcher import process_keyword, SERPSearcher

def handler(request):
    if request.method != 'POST':
        return json.dumps({'error': 'Method not allowed'}), 405, {'Content-Type': 'application/json'}

    try:
        # Parse the request body
        content_length = int(request.headers.get('Content-Length', 0))
        body = request.rfile.read(content_length).decode('utf-8')
        data = json.loads(body)
        
        keyword = data.get('keyword')
        
        if not keyword:
            return json.dumps({'error': 'Keyword is required'}), 400, {'Content-Type': 'application/json'}

        # Initialize searcher with environment variables
        searcher = SERPSearcher(api_key=os.getenv('SERPAPI_KEY'))
        
        # Process the keyword using your existing function
        result = process_keyword(keyword, searcher)
        
        # Convert the result to a JSON-serializable format if needed
        if hasattr(result, '__dict__'):
            result = result.__dict__
            
        return json.dumps({
            'status': 'success',
            'data': result
        }), 200, {'Content-Type': 'application/json'}

    except json.JSONDecodeError:
        return json.dumps({'error': 'Invalid JSON'}), 400, {'Content-Type': 'application/json'}
    except Exception as e:
        return json.dumps({'error': str(e)}), 500, {'Content-Type': 'application/json'}

# This allows the function to work with Vercel's Python runtime
def lambda_handler(event, context):
    class Request:
        def __init__(self, event):
            self.method = event['httpMethod']
            self.headers = event.get('headers', {})
            self.rfile = self
            self._content = event.get('body', '{}').encode('utf-8')
            self._content_consumed = False
            
        def read(self, size=-1):
            if self._content_consumed:
                return b''
            self._content_consumed = True
            return self._content
            
    request = Request(event)
    response = handler(request)
    
    if len(response) == 3:
        body, status_code, headers = response
    else:
        body, status_code = response
        headers = {}
        
    return {
        'statusCode': status_code,
        'headers': {**headers, 'Content-Type': 'application/json'},
        'body': body if isinstance(body, str) else json.dumps(body)
    }
