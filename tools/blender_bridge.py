"""Client for Blender Lab's existing null-delimited execute bridge; not a server."""
import argparse
import json
from pathlib import Path
import socket
import time

parser = argparse.ArgumentParser()
parser.add_argument('--file',required=True,type=Path)
parser.add_argument('--port',type=int,default=9876)
parser.add_argument('--timeout',type=float,default=120)
args = parser.parse_args()
code = '__file__ = ' + repr(str(args.file.resolve())) + '\n' + args.file.read_text(encoding='utf-8')
request = {'type':'execute','strict_json':True,'code':code}
deadline = time.monotonic()+15
while True:
    try:
        connection = socket.create_connection(('127.0.0.1',args.port),timeout=5)
        break
    except (ConnectionRefusedError, socket.timeout):
        if time.monotonic() >= deadline:
            raise
        time.sleep(.2)
with connection:
    connection.settimeout(args.timeout)
    connection.sendall(json.dumps(request).encode('utf-8')+b'\0')
    chunks = bytearray()
    while b'\0' not in chunks:
        block = connection.recv(65536)
        if not block:
            raise RuntimeError('Bridge disconnected before completing its response')
        chunks.extend(block)
response = json.loads(chunks.split(b'\0',1)[0])
print(json.dumps(response,ensure_ascii=False,indent=2))
if response.get('status') != 'ok':
    raise SystemExit(1)
