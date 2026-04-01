#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
简单HTTP服务器 - 用于启动前端应用
"""

import http.server
import socketserver
import webbrowser
import os
import sys
from pathlib import Path

PORT = 3001
DIRECTORY = Path(__file__).parent

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DIRECTORY), **kwargs)
    
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
        super().end_headers()
    
    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

def main():
    os.chdir(DIRECTORY)
    
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        url = f"http://localhost:{PORT}"
        print(f"\n{'='*60}")
        print(f"  历史研究AI工具 - 前端服务已启动")
        print(f"{'='*60}")
        print(f"\n  访问地址: {url}")
        print(f"  服务目录: {DIRECTORY}")
        print(f"\n  按 Ctrl+C 停止服务")
        print(f"{'='*60}\n")
        
        try:
            webbrowser.open(url)
        except:
            pass
        
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n\n服务已停止")
            sys.exit(0)

if __name__ == "__main__":
    main()
