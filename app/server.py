#!/usr/bin/env python3
"""No-cache static server for the Starter Lab app. Serves this directory on :4788.
Run: python3 server.py   ->   http://localhost:4788/lab.built.html
"""
import http.server, socketserver, os

os.chdir(os.path.dirname(os.path.abspath(__file__)))

class H(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0')
        self.send_header('Pragma', 'no-cache')
        super().end_headers()
    def log_message(self, *a):
        pass

http.server.ThreadingHTTPServer.allow_reuse_address = True
with http.server.ThreadingHTTPServer(("", 4788), H) as httpd:  # threaded: handles concurrent requests (cross-browser e2e)
    print("Starter Lab -> http://localhost:4788/lab.built.html")
    httpd.serve_forever()
