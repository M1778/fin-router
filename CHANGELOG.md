# Changelog

## 0.1.0 — 2026-10-23 (first build, day 1 of the weekly cycle)

- Route table with literal, `:param`, and trailing `*wildcard`
  segments; first-match-wins; method `"*"` matches any method.
- `router_match` with 200/404/405 semantics and deduped `Allow` list.
- `router_dispatch`: match → middleware chain → handler, with
  short-circuit middleware.
- Groups (`router_group` / `group_add`) with slash-safe prefix joins.
- Query parsing with `%XX` + `+` decoding; path params `%XX`-decoded.
- Middleware helpers: CORS origin, bearer-token check, log lines.
- Example zhttp server + real-HTTP smoke test.
- Verified: 91/91 unit assertions, 20/20 real-HTTP smoke assertions
  (finc 0.4.0, contract 3).
