#!/usr/bin/env python3
"""Smoke test for fin-router's example server: builds the binary (deps
via env vars, see below), boots it on a fresh port (fresh per run —
zhttp's server has no SO_REUSEADDR, so a same-port restart within
~60s of serving a client fails to bind), and drives every route over
real HTTP. Fails loudly.

Dep dirs (override with env vars; defaults are the fin-dev workspace
siblings, where the libraries live until Eleanor creates their repos):
  FINC, FIN_ROUTER, FIN_ZHTTP
"""
import http.client
import os
import socket
import subprocess
import sys
import time

passed = 0
failed = 0


def check(name, cond, extra=""):
    global passed, failed
    if cond:
        passed += 1
    else:
        failed += 1
        print(f"FAIL {name} {extra}")


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
BIN = os.path.join(ROOT, "router_server")

WS = os.path.expanduser("~/workspace/fin-dev")
FINC = os.environ.get("FINC") or os.path.join(
    WS, "tester-1", "Fin", "build", "finc")
FIN_ROUTER = os.environ.get("FIN_ROUTER") or os.path.join(ROOT, "src")
FIN_ZHTTP = os.environ.get("FIN_ZHTTP") or os.path.join(
    WS, "builder-1", "zhttp", "src")
for label, d in (("finc", FINC), ("router src", FIN_ROUTER),
                 ("zhttp src", FIN_ZHTTP)):
    if not os.path.exists(d):
        print(f"missing dep {label}: {d}")
        sys.exit(2)

build = subprocess.run(
    [FINC, "-I", FIN_ROUTER, "-I", FIN_ZHTTP,
     os.path.join(ROOT, "examples", "router_server.fin"),
     "-o", BIN],
    capture_output=True, text=True)
if build.returncode != 0:
    print("BUILD FAILED")
    print(build.stdout)
    print(build.stderr)
    sys.exit(2)

port = free_port()
proc = subprocess.Popen(
    ["stdbuf", "-o0", BIN, str(port)],
    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

try:
    # Wait until the port accepts connections (banner may be buffered).
    deadline = time.time() + 15
    while True:
        try:
            s = socket.create_connection(("127.0.0.1", port), timeout=1)
            s.close()
            break
        except OSError:
            if time.time() > deadline:
                print("server did not come up")
                sys.exit(2)
            time.sleep(0.2)

    def req(method, path, body=None, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request(method, path, body=body,
                     headers=headers or {})
        resp = conn.getresponse()
        data = resp.read().decode("utf-8", "replace")
        hdrs = {k.lower(): v for k, v in resp.getheaders()}
        conn.close()
        return resp.status, data, hdrs

    st, body, _ = req("GET", "/")
    check("GET /", st == 200 and body == "fin-router demo\n", f"{st} {body!r}")
    st, body, _ = req("GET", "/users")
    check("GET /users", st == 200 and body == "user list\n", f"{st} {body!r}")
    st, body, _ = req("GET", "/users/42")
    check("GET /users/42", st == 200 and body == "user 42\n", f"{st} {body!r}")
    st, body, _ = req("GET", "/users/42/posts/7")
    check("nested params", st == 200 and body == "user 42 post 7\n",
          f"{st} {body!r}")
    st, body, _ = req("GET", "/users/42?tab=posts")
    check("query ignored for routing", st == 200 and body == "user 42\n",
          f"{st} {body!r}")
    st, body, _ = req("GET", "/users/%34%32")
    check("percent-decoded param", st == 200 and body == "user 42\n",
          f"{st} {body!r}")
    st, body, _ = req("POST", "/users", body="hello-body")
    check("POST /users echo", st == 201 and body == "hello-body",
          f"{st} {body!r}")
    st, body, _ = req("GET", "/files/a/b.txt")
    check("wildcard", st == 200 and body == "file a/b.txt\n", f"{st} {body!r}")
    st, body, _ = req("GET", "/api/health")
    check("group health", st == 200 and body == "ok\n", f"{st} {body!r}")
    st, body, _ = req("GET", "/api/users/9")
    check("group param", st == 200 and body == "api user 9\n", f"{st} {body!r}")
    st, body, _ = req("GET", "/missing")
    check("404", st == 404 and body == "not found\n", f"{st} {body!r}")
    st, body, hdrs = req("DELETE", "/users/1")
    check("405", st == 405 and body == "method not allowed\n",
          f"{st} {body!r}")
    check("405 Allow", hdrs.get("allow") == "GET",
          f"{hdrs.get('allow')!r}")
    st, body, hdrs = req("DELETE", "/users")
    check("405 Allow multi", st == 405 and hdrs.get("allow") == "GET, POST",
          f"{st} {hdrs.get('allow')!r}")
    st, body, _ = req("POST", "/users/42", body="x")
    check("405 on param route", st == 405, f"{st}")
    st, body, _ = req("GET", "/admin/stats")
    check("admin no auth 401", st == 401 and body == "unauthorized\n",
          f"{st} {body!r}")
    st, body, _ = req("GET", "/admin/stats",
                      headers={"Authorization": "Bearer demo-token"})
    check("admin with token", st == 200 and body == "admin stats\n",
          f"{st} {body!r}")
    st, body, _ = req("GET", "/admin/stats",
                      headers={"Authorization": "Bearer wrong"})
    check("admin wrong token 401", st == 401, f"{st}")
    st, body, hdrs = req("GET", "/", headers={"Origin": "https://a.com"})
    check("CORS header", hdrs.get("access-control-allow-origin") == "*",
          f"{hdrs.get('access-control-allow-origin')!r}")
    st, body, _ = req("GET", "/users/")
    check("trailing slash 404", st == 404, f"{st}")
finally:
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()

print(f"SMOKE {'OK' if failed == 0 else 'FAILED'}: "
      f"{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
