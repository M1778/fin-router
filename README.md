# fin-router

An HTTP router library for [Fin](https://github.com/M1778/Fin). Route
patterns with path params, method matching, middleware, and grouping —
verified with unit tests and real-HTTP smoke tests against a running
server.

> **Verification status:** ✅ VERIFIED — built with `finc 0.4.0`
> (contract 3); 91/91 unit assertions pass, 20/20 real-HTTP smoke
> assertions pass. CI builds finc from source and re-runs both.

## Install

Requires the `finn` package manager (https://github.com/M1778/finn):

```sh
finn add M1778/fin-router
```

Until finn publishes it, use a checkout and pass `-I` (see "Build").

## Quick example

```fin
import {
    Router, RtCtx, RtResp, RtMwOut,
    router_new, router_add, router_use, router_dispatch,
    router_ctx_param
} from router::fin;
import { clone, free_str } from strings::std;

fun show_user(ctx: &RtCtx) <RtResp> {
    // Params are borrowed: clone anything returned.
    return RtResp{status: 200, body: clone(router_ctx_param(ctx, "id")),
                  content_type: clone("text/plain")};
}

fun logger(ctx: &RtCtx) <RtMwOut> {
    printf("%s %s\n", ctx.method, ctx.path);
    return RtMwOut{stop: false, status: 0, body: clone(""),
                   content_type: clone("")};
}

fun main() <noret> {
    let r <&Router> = router_new();
    router_add(r, "GET", "/users/:id", show_user);
    router_use(r, logger);
    let resp <RtResp> = router_dispatch(r, "GET", "/users/42", "");
    printf("%d %s\n", resp.status, resp.body);
    free_str(resp.body);
    free_str(resp.content_type);
}
```

Wire it to a real server by passing `req.method`, `req.target`, and
`req.body` from zhttp (see `examples/router_server.fin`, which serves
all of the routes below over real HTTP).

## Route patterns

| Pattern | Matches | Captures |
|---|---|---|
| `/users` | `/users` exactly | — |
| `/users/:id` | one nonempty segment | `id` |
| `/users/:id/posts/:pid` | two params | `id`, `pid` |
| `/files/*rest` | `/files` + anything, slashes included | `rest` |
| `/dl/*` | same, bare wildcard | `*` |
| `/` | root only | — |

Rules:

- Patterns start with `/`. Empty segments are invalid (`router_add`
  returns -1 for `/users/`, `/users//x`, `/users/:`, `/files/*/x`,
  a missing leading slash, or an empty method).
- First registered match wins. Method `"*"` matches any method.
- Matching is exact and case-sensitive; `get` does not match `GET`.
- The `?query` (and any `#fragment`) is stripped before matching.
- Param values are %-decoded (`%XX` only; `+` stays a literal `+`).
  A wildcard may capture an empty rest (`/files` matches
  `/files/*rest` with `rest == ""`).

## API reference

**Lifecycle**

- `router_new() <&Router>` — empty table.
- `router_free(r)` — frees stored strings and collections.
- `router_count(r) <int>`, `router_route_method(r, i)`,
  `router_route_pattern(r, i)` — introspection (borrowed strings).

**Registration** (returns the route index, or -1 when invalid)

- `router_add(r, method, pattern, handler) <int>`
- `router_group(r, prefix) <&RouteGroup>` +
  `group_add(g, method, pattern, handler) <int>` — the group prefix is
  joined to every pattern; pattern `"/"` maps to the prefix itself, so
  a group's root route is the prefix (`/api`, not `/api/`). A prefix
  with a trailing slash (`/v2/`) joins cleanly. Free with `group_free`.
- `router_use(r, mw)` — append a middleware fn to the chain.

**Matching**

- `router_match(r, method, target) <RtMatch>` — `found`, `status`
  (200 / 404 / 405), `index` (-1 when not found), `allow`
  (comma-joined methods for 405s, deduped, registration order),
  `names`/`values` (fresh param collections). Free with
  `router_free_match`.
- `router_param(m, name)` (borrowed, `""` when absent),
  `router_param_has`, `router_param_count`, `router_param_name`,
  `router_param_value`.
- `router_ctx_param(ctx, name)`, `router_ctx_param_has` — the same
  lookup on a handler/middleware context.
- `router_target_path(target)`, `router_target_query(target)` — fresh
  strings; the query is raw (use the query helpers to decode).

**Query values** (fresh decoded strings; caller frees)

- `router_query_get(query, key)` — first value, `+` → space,
  `%XX` decoded; a bare key counts as present with `""`; a missing key
  returns fresh `""`.
- `router_query_has(query, key) <bool>`.

**Dispatch** (the full pipeline: match → middleware → handler)

- `router_dispatch(r, method, target, body) <RtResp>` — the returned
  body and content_type are ALWAYS fresh; free them after writing.
  404/405 bodies are `"not found\n"` / `"method not allowed\n"`
  (text/plain). A middleware short-circuit returns the middleware's
  own status/body/content_type.

**Middleware helpers** (transport-independent building blocks)

- `router_cors_origin(origin, allowed)` — fresh: `"*"` when the policy
  allows any origin, the request origin when it matches, else `""`.
- `router_auth_bearer(auth_header, token)` — true iff the header is
  exactly `"Bearer <token>"`; an empty token never matches.
- `router_log_line(method, path, status)` — fresh `"METHOD path ->
  STATUS"` line.

## Middleware semantics

Middleware runs AFTER a successful match, in registration order, with
full params in the ctx. A middleware returns `RtMwOut{stop, status,
body, content_type}`: `stop=false` continues, `stop=true`
short-circuits dispatch with that status/body. 404/405 responses bypass
middleware — put request logging that must see 404s in the app around
`router_dispatch`, not in the chain.

Handler and middleware bodies/content-types MUST be fresh (clone
literals) — dispatch frees middleware results on continue and
transfers them on stop, and the app frees dispatch results. This is the
same "returned strings are heap" rule the rest of the Fin ecosystem
uses.

## Ownership summary

| Value | Owner | Free with |
|---|---|---|
| Stored methods/patterns | router (cloned at add) | `router_free` |
| Match params | caller (fresh) | `router_free_match` |
| `router_param` / `router_ctx_param` results | borrowed | never free |
| `router_query_get`, `router_cors_origin`, `router_log_line`, `router_target_*` | caller (fresh) | `free_str` |
| Dispatch `RtResp` body/content_type | caller (fresh) | `free_str` |
| Handler/middleware returns | must be fresh | (dispatch/app frees) |
| `RtCtx` strings | borrowed for the call | never free; clone to keep |

## Build and test

```sh
# Unit tests (91 assertions; any failure aborts with blame)
finc -I src tests/test_router.fin -o test_router && ./test_router

# Example server + real-HTTP smoke test (20 assertions)
# FIN_ZHTTP defaults to the fin-dev workspace sibling checkout.
python3 tests/smoke.py
# ...or both at once:
sh tests/run_tests.sh

# Example server by hand (zhttp is a sibling checkout for now)
finc -I src -I <zhttp>/src examples/router_server.fin -o router_server
./router_server 8080
curl localhost:8080/users/42
```

## Known limitations (v0.1.0, honest list)

- **Middleware cannot see request headers.** `RtCtx` carries method,
  path, query, body, and params — but no headers, because the core is
  transport-independent and zhttp's `HttpHeaders` type would couple it
  to zhttp. Header-based gates (the example's `/admin/*` bearer check)
  therefore live in app code around `router_dispatch`, as
  `examples/router_server.fin` demonstrates. A future version may add
  an opt-in headers carrier to `RtCtx`.
- **No trailing-slash policy.** `/users/` and `/users` are different
  routes; there is no redirect or normalization option yet.
- **No HEAD-falls-back-to-GET.** `HEAD` needs its own route.
- **No fn-pointer-free fallback needed:** handler/middleware fns ARE
  real stored fn values (proven to lower through imports in finc
  0.4.0 — a stored fn must be called through a local binding, which
  the library does internally).
- **Single-threaded assumption.** The router holds no locks; a
  multi-threaded server must serialize `router_dispatch` or give each
  thread its own router (registration is not thread-safe either).
- `%00` in a param/query value decodes to NUL and truncates the value
  (C-string semantics) — do not use decoded values as binary data.

## License

MIT — see `LICENSE`.
