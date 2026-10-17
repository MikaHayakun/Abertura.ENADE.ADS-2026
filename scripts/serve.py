#!/usr/bin/env python3
"""Local project preview, including byte ranges for video seeking."""
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import argparse
import json
import re

ROOT = Path(__file__).resolve().parents[1]


class Handler(SimpleHTTPRequestHandler):
    def __init__(self,*args,**kwargs):
        self.byte_range = None
        super().__init__(*args,directory=str(ROOT),**kwargs)

    def do_GET(self):
        if self.path == '/health':
            data = json.dumps({'project':'Abertura.ENADE.ADS-2026','video':(ROOT/'output/ENADE.ADS-2026-abertura-3D-dupla-dinamica.mp4').is_file()}).encode()
            self.send_response(200)
            self.send_header('Content-Type','application/json')
            self.send_header('Content-Length',str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        super().do_GET()

    def send_head(self):
        if self.path.split('?',1)[0].endswith('.mp4'):
            path = Path(self.translate_path(self.path))
            if not path.is_file():
                self.send_error(404)
                return None
            size = path.stat().st_size
            start,end = 0,size-1
            header = self.headers.get('Range')
            if header:
                match = re.fullmatch(r'bytes=(\d*)-(\d*)',header)
                if not match or not any(match.groups()):
                    self.send_error(416)
                    return None
                if match[1]:
                    start = int(match[1]);end = min(int(match[2]) if match[2] else end,end)
                else:
                    start = max(0,size-int(match[2]))
                if start > end or start >= size:
                    self.send_response(416)
                    self.send_header('Content-Range',f'bytes */{size}')
                    self.send_header('Content-Length','0')
                    self.end_headers()
                    return None
            self.send_response(206 if header else 200)
            self.send_header('Content-Type','video/mp4')
            self.send_header('Accept-Ranges','bytes')
            self.send_header('Content-Length',str(end-start+1))
            if header:self.send_header('Content-Range',f'bytes {start}-{end}/{size}')
            self.end_headers()
            stream=path.open('rb');stream.seek(start)
            self.byte_range=(start,end)
            return stream
        return super().send_head()

    def copyfile(self,source,outputfile):
        try:
            if self.byte_range:
                start,end=self.byte_range
                remaining=end-start+1
                while remaining:
                    chunk=source.read(min(65536,remaining))
                    if not chunk:break
                    outputfile.write(chunk)
                    remaining-=len(chunk)
            else:super().copyfile(source,outputfile)
        except (BrokenPipeError,ConnectionResetError):
            pass


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--port',type=int,default=4173)
    args=parser.parse_args()
    server=ThreadingHTTPServer(('127.0.0.1',args.port),Handler)
    print(f'ENADE.ADS–2026: http://localhost:{args.port}',flush=True)
    server.serve_forever()
