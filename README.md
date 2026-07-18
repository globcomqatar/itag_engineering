# ITAG Engineering Management

Engineering Management and Product Lifecycle control layer for ERPNext Manufacturing
(valve manufacturing), built per `ITAG_Engineering_Management_Master_Roadmap_v1.0(Approved).md`.

This is Build `ITAG-0.1.0` — Application Foundation. See the roadmap document (Engineering
Management working directory) and `doc/ITAG_Decisions.md` (bench root) for the full
program plan and the Phase 0 decisions this build implements.

## What this build provides

- App foundation, installable and migratable on Frappe v15 / ERPNext v15.
- Engineering Settings (single DocType) with a Validate Configuration action that gates
  production-blocking flags behind a "Ready" readiness check.
- The 16 engineering roles used throughout the roadmap, created idempotently on install.
- A base "ITAG Engineering Management" workspace shell.
- Foundation code: standard API response envelope, base exception/error-code pattern,
  a dedicated logger channel, a compatibility-mode service skeleton, and a `ping` health
  check API.

## Local development

This app runs inside the `frappe-docker_devcontainer-frappe-1` container, bench at
`/workspace/development/frappe-bench`, site `frappedevelopment.localhost`.

Install app (already done for this build):
```
bench --site frappedevelopment.localhost install-app itag_engineering
```

Run the test suite:
```
bench --site frappedevelopment.localhost run-tests --app itag_engineering
```

Migrate:
```
bench --site frappedevelopment.localhost migrate
```

## License

MIT
