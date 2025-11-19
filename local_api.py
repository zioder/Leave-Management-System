"""
Simple local API server to run the backend without deploying to AWS Lambda.
Listens on port 3001 and mimics the Lambda Function URL behavior.
"""
import json
import sys
import traceback
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from typing import Any, Dict

# Import the lambda handler
# Ensure src is in path
sys.path.append(".")
from src.agent.lambda_handler import lambda_handler

PORT = 3001

class LocalLambdaHandler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-Requested-With')
        self.end_headers()

    def do_GET(self):
        self.handle_request("GET")

    def do_POST(self):
        self.handle_request("POST")

    def handle_request(self, method):
        try:
            # Construct a mock Lambda event
            parsed_url = urlparse(self.path)
            path = parsed_url.path
            
            # Read body if present
            body = None
            if "Content-Length" in self.headers:
                content_length = int(self.headers["Content-Length"])
                body = self.rfile.read(content_length).decode("utf-8")
            
            event = {
                "requestContext": {
                    "http": {
                        "method": method,
                        "path": path
                    }
                },
                "body": body,
                "headers": dict(self.headers),
                "queryStringParameters": parse_qs(parsed_url.query)
            }
            
            # Call the actual Lambda handler
            response = lambda_handler(event, None)
            
            # Send response
            status_code = response.get("statusCode", 200)
            self.send_response(status_code)
            
            # Send headers
            for k, v in response.get("headers", {}).items():
                self.send_header(k, v)
            self.end_headers()
            
            # Send body
            resp_body = response.get("body", "")
            if isinstance(resp_body, str):
                self.wfile.write(resp_body.encode("utf-8"))
            else:
                self.wfile.write(json.dumps(resp_body).encode("utf-8"))
                
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            error = {"error": str(e), "traceback": traceback.format_exc()}
            self.wfile.write(json.dumps(error).encode("utf-8"))
            print(f"Error processing request: {e}")

def run_server():
    print(f"🚀 Starting local backend on http://localhost:{PORT}")
    print("   Press Ctrl+C to stop")
    server = HTTPServer(('localhost', PORT), LocalLambdaHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 Server stopped.")
        server.server_close()

if __name__ == "__main__":
    run_server()

