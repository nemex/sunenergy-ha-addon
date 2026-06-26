import os
import json
from http.server import BaseHTTPRequestHandler, HTTPServer

STATE_PATH = "/data/controller_state.json"
HTML_PATH = "/app/index.html"

class DashboardHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Suppress logging every HTTP request to avoid cluttering HA addon logs
        pass

    def do_GET(self):
        # Normalise path (strip query params, trailing slashes)
        path = self.path.split('?')[0]
        
        # Watchdog endpoint
        if path == "/state":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status": "ok"}')
            return

        # API endpoint
        elif path in ("/api/data", "/api/data/"):
            if os.path.exists(STATE_PATH):
                try:
                    with open(STATE_PATH, "r", encoding="utf-8") as f:
                        data = f.read()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(data.encode("utf-8"))
                    return
                except Exception as e:
                    self.send_response(500)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(f'{{"error": "{str(e)}"}}'.encode("utf-8"))
                    return
            else:
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                # Return standard structure during initial boot before controller creates the file
                mock_data = {
                    "timestamp": 0.0,
                    "grid_power": 0.0,
                    "grid_source": "Warte auf Controller-Start...",
                    "grid_trend": [],
                    "hms_2000": {"power": 0, "limit": 2000, "ratio": 0.5},
                    "hms_1600": {"power": 0, "limit": 1600, "ratio": 0.5},
                    "soc_l1": 0.0,
                    "soc_l2": 0.0,
                    "se_l1_op": 0.0,
                    "se_l2_op": 0.0,
                    "logs": ["Initialisiere Controller..."]
                }
                self.wfile.write(json.dumps(mock_data).encode("utf-8"))
                return

        # Main HTML page
        elif path in ("/", "/index.html", "/index", "/api/hassio_ingress/"):
            # Serve index.html
            html_file = HTML_PATH
            # Fallback for local development
            if not os.path.exists(html_file):
                html_file = "index.html"
                
            if os.path.exists(html_file):
                try:
                    with open(html_file, "r", encoding="utf-8") as f:
                        content = f.read()
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(content.encode("utf-8"))
                    return
                except Exception as e:
                    self.send_response(500)
                    self.end_headers()
                    self.wfile.write(f"Error reading index.html: {e}".encode("utf-8"))
                    return
            else:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b"index.html not found.")
                return
        
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not Found")

def run(port=8765):
    server_address = ('', port)
    httpd = HTTPServer(server_address, DashboardHandler)
    print(f"Web UI server running on port {port}...")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    httpd.server_close()
    print("Server stopped.")

if __name__ == '__main__':
    run()
