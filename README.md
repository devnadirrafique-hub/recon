# recon — read-only recon tools for the Hermes Agent

Three tools that do the first steps of a bug-bounty recon, the way a hunter
does them by hand. The agent asks for a domain or a JavaScript file; the
plugin returns real public data. It only looks. It never touches, never logs
in, never attacks anything.

## The tools

- **recon_subdomains** — subdomains of a domain, from public certificate
  records (crt.sh). No key, no login. Give a bare domain:
  `{"domain": "example.com"}`
- **recon_wayback_urls** — archived pages of a domain, from the Wayback
  Machine's public index. Give a bare domain:
  `{"domain": "example.com"}`
- **recon_js_endpoints** — API paths and absolute URLs quoted inside a
  JavaScript file. Give the file's address:
  `{"url": "https://cdn.example.com/app.js"}`

Every tool answers with JSON: `{"success": true, "tool": ..., "source": ...,
"count": N, "results": [...]}` — or `{"success": false, "error": ...}` when
the source did not answer. A failure is an answer, never a crash and never a
guessed result.

## Install

Once the plugin is in the Hermes plugin catalog:

```sh
hermes plugins install devnadirrafique-hub/recon
```

Then enable it in `~/.hermes/config.yaml` under `plugins.enabled` and restart
the agent.

## What it does not do

- No port scanning, no brute-forcing, no logins, no exploitation, no secrets.
  It only reads public sources, only on targets you point it at.
- It finds leads, not vulnerabilities. A subdomain, an old page, or a path in
  a JavaScript file is a starting point — a finding needs the input accepted
  and the consequence verified, like any other hunt work.
- Use it only on targets you are authorised to test, in scope, with
  permission. The same rule as any recon: scope is the hard limit.

## Honest limits

- It depends on public sources. If crt.sh or the Wayback Machine is down or
  slow, the tool says so instead of guessing. The archive is famously slow:
  the archived-pages tool waits up to 60 seconds for an answer.
- The JavaScript tool reads quoted strings only. A path built at runtime from
  pieces will not show up, and a found path may be dead, renamed, or
  unreachable — check it before trusting it.
- Results are capped (500 subdomains, 500 archived pages, 200 endpoints) so a
  huge answer does not flood the agent's context.

## How it is built

Standard library only — no extra dependencies, no network beyond the three
public sources, no credentials anywhere. The engines in `recon/` have no
Hermes dependency and are unit-tested with mocked HTTP; the wiring in
`__init__.py` only registers the tools with Hermes.
