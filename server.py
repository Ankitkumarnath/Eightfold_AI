import http.server
import socketserver
import json
import os
import subprocess
import cgi
import tempfile
import urllib.parse

PORT = 8080

class ResolutionHandler(http.server.SimpleHTTPRequestHandler):
    def do_POST(self):
        if self.path == '/api/resolve':
            # Parse multipart form data
            content_type = self.headers.get('Content-Type')
            if not content_type or not content_type.startswith('multipart/form-data'):
                self.send_response(400)
                self.end_headers()
                return

            length = int(self.headers.get('content-length', 0))
            body = self.rfile.read(length)

            # Manually extract files (very simplified for this assignment)
            # Since we just want to run main.py, we can just grab the boundaries
            boundary = content_type.split('=')[1].encode()
            parts = body.split(b'--' + boundary)

            wd_path, gh_path, pdf_path, github_path, notes_path = None, None, None, None, None

            for part in parts:
                if b'filename="' in part:
                    # Extract filename and content
                    header_end = part.find(b'\r\n\r\n')
                    if header_end == -1: continue
                    headers = part[:header_end]
                    content = part[header_end+4:-2] # remove trailing \r\n
                    
                    if b'name="workday"' in headers and len(content) > 0:
                        wd_path = tempfile.mktemp(suffix=".csv")
                        with open(wd_path, 'wb') as f: f.write(content)
                    elif b'name="greenhouse"' in headers and len(content) > 0:
                        gh_path = tempfile.mktemp(suffix=".json")
                        with open(gh_path, 'wb') as f: f.write(content)
                    elif b'name="resume"' in headers and len(content) > 0:
                        pdf_path = tempfile.mktemp(suffix=".pdf")
                        with open(pdf_path, 'wb') as f: f.write(content)
                    elif b'name="github"' in headers and len(content) > 0:
                        github_path = tempfile.mktemp(suffix=".json")
                        with open(github_path, 'wb') as f: f.write(content)
                    elif b'name="notes"' in headers and len(content) > 0:
                        notes_path = tempfile.mktemp(suffix=".txt")
                        with open(notes_path, 'wb') as f: f.write(content)

            # Run the CLI using venv python to ensure dependencies are found
            cmd = ["./venv/bin/python", "main.py", "--output", "data/output.json"]
            if wd_path: cmd.extend(["--workday", wd_path])
            if gh_path: cmd.extend(["--greenhouse", gh_path])
            if pdf_path: cmd.extend(["--resume", pdf_path])
            if github_path: cmd.extend(["--github", github_path])
            if notes_path: cmd.extend(["--notes", notes_path])

            subprocess.run(cmd, check=False)

            # Cleanup temp files
            if wd_path and os.path.exists(wd_path): os.unlink(wd_path)
            if gh_path and os.path.exists(gh_path): os.unlink(gh_path)
            if pdf_path and os.path.exists(pdf_path): os.unlink(pdf_path)
            if github_path and os.path.exists(github_path): os.unlink(github_path)
            if notes_path and os.path.exists(notes_path): os.unlink(notes_path)

            # Return the output.json
            if os.path.exists("data/output.json"):
                with open("data/output.json", "r") as f:
                    data = json.load(f)
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"status": "success", "data": data}).encode())
            else:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(b'{"status": "error"}')

        else:
            super().do_POST()

    def do_GET(self):
        # Serve index.html at root
        if self.path == '/':
            self.path = '/static/index.html'
        return super().do_GET()

with socketserver.TCPServer(("", PORT), ResolutionHandler) as httpd:
    print(f"Serving UI at http://localhost:{PORT}")
    httpd.serve_forever()
