# -*- coding: utf-8 -*-
"""serve.py — docs/ on a local port, for looking at the thing before it ships."""
import functools, http.server, socketserver, sys
from pathlib import Path

DOCS = Path(__file__).resolve().parent.parent / "docs"
port = int(sys.argv[1]) if len(sys.argv) > 1 else 8821
H = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(DOCS))
socketserver.TCPServer.allow_reuse_address = True
print("docs/ on http://localhost:%d" % port)
socketserver.TCPServer(("", port), H).serve_forever()
