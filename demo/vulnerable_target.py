#!/usr/bin/env python3
# ruff: noqa: PLR0912, PLW1510, PTH123, S602, S608, T201
"""Deliberately vulnerable demo target for BoomHackerWhite.

WARNING: This server is intentionally insecure. Run it ONLY on localhost
or an isolated network, only while testing, and kill it afterwards.
Never deploy it, never expose it to the internet.

It exists so a fresh install can prove itself end to end: point
BoomHackerWhite at it and watch real findings come back, instead of
wondering whether the tool "does anything".

Vulnerabilities on purpose:
  - Reflected XSS            GET /search?q=<script>...
  - SQL injection            GET /login?user=' OR '1'='1' -- &pass=x
  - IDOR / broken access     GET /user?id=1 (no auth, sequential ids)
  - Command injection        GET /ping?host=127.0.0.1;id
  - Path traversal           GET /page?file=../demo/vulnerable_target.py

Usage:
  python3 demo/vulnerable_target.py [--host 127.0.0.1] [--port 8899]
"""

import argparse
import html
import sqlite3
import subprocess
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse


DB = sqlite3.connect(":memory:")
DB.execute("CREATE TABLE users (id INTEGER, name TEXT, password TEXT, email TEXT)")
DB.executemany(
    "INSERT INTO users VALUES (?, ?, ?, ?)",
    [
        (1, "admin", "s3cr3t-admin-pass", "admin@example.com"),
        (2, "alice", "alice-password", "alice@example.com"),
        (3, "bob", "bob-password", "bob@example.com"),
    ],
)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args: object) -> None:
        pass

    def _send(self, body: str, status: int = 200) -> None:
        data = body.encode()
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        path = parsed.path

        if path == "/":
            self._send(
                "<h1>BHW Demo Shop</h1><ul>"
                "<li><a href='/search?q=shoes'>Search</a></li>"
                "<li><a href='/login'>Login</a></li>"
                "<li><a href='/user?id=2'>My profile</a></li>"
                "<li><a href='/ping?host=127.0.0.1'>Ping tool</a></li>"
                "<li><a href='/page?file=welcome.txt'>Welcome page</a></li></ul>"
            )
        elif path == "/search":
            q = params.get("q", [""])[0]
            # VULNERABLE: reflected XSS — q echoed without escaping.
            self._send(f"<h1>Results for: {q}</h1><p>No products found.</p>")
        elif path == "/login":
            user = params.get("user", [""])[0]
            password = params.get("pass", [""])[0]
            if not user:
                self._send(
                    "<form>Username <input name='user'> Password "
                    "<input name='pass'> <button>Login</button></form>"
                )
                return
            # VULNERABLE: SQL injection — string-formatted query.
            query = f"SELECT id, name FROM users WHERE name = '{user}' AND password = '{password}'"
            try:
                rows = DB.execute(query).fetchall()
            except sqlite3.Error as e:
                self._send(f"<p>Database error: {html.escape(str(e))}</p>", 500)
                return
            if rows:
                self._send(f"<h1>Welcome, {rows[0][1]}!</h1>")
            else:
                self._send("<p>Invalid credentials.</p>", 401)
        elif path == "/user":
            uid = params.get("id", ["0"])[0]
            # VULNERABLE: IDOR — any id returns that user, no authentication.
            row = DB.execute("SELECT id, name, email FROM users WHERE id = ?", (uid,)).fetchone()
            if row:
                self._send(f"<h1>Profile</h1><p>{row[1]} — {row[2]}</p>")
            else:
                self._send("<p>No such user.</p>", 404)
        elif path == "/ping":
            host = params.get("host", ["127.0.0.1"])[0]
            # VULNERABLE: OS command injection — shell=True with raw input.
            out = subprocess.run(
                f"ping -c 1 {host}", shell=True, capture_output=True, text=True, timeout=20
            )
            self._send(f"<pre>{html.escape(out.stdout + out.stderr)}</pre>")
        elif path == "/page":
            name = params.get("file", ["welcome.txt"])[0]
            # VULNERABLE: path traversal — no sanitization of `name`.
            try:
                with open(f"demo/pages/{name}", encoding="utf-8") as f:
                    content = f.read()
                self._send(f"<pre>{content}</pre>")
            except OSError:
                # Fall back to reading relative to CWD for the traversal demo.
                try:
                    with open(name, encoding="utf-8") as f:
                        content = f.read()
                    self._send(f"<pre>{html.escape(content)}</pre>")
                except OSError:
                    self._send("<p>Page not found.</p>", 404)
        else:
            self._send("<p>Not found.</p>", 404)


def main() -> None:
    parser = argparse.ArgumentParser(description="BHW deliberately vulnerable demo target")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8899)
    args = parser.parse_args()
    server = HTTPServer((args.host, args.port), Handler)
    print(f"Demo target listening on http://{args.host}:{args.port} (Ctrl-C to stop)")
    print("WARNING: deliberately vulnerable — localhost only, kill it when done.")
    server.serve_forever()


if __name__ == "__main__":
    main()
