# ITAG Engineering Management

Engineering Management and Product Lifecycle control layer for ERPNext Manufacturing
(valve manufacturing), built per `ITAG_Engineering_Management_Master_Roadmap_v1.0(Approved).md`.

Build `ITAG-0.1.0` (Application Foundation) and Build `ITAG-0.2.0` (Item Engineering and
Coding) are both implemented. See the roadmap document (Engineering
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

## Build ITAG-0.2.0 — Item Engineering and Coding

- Item Code Rule (+ segment child table) with server-side preview/resolution (`item_code_service.py`).
- Item Code Reservation with collision-safe sequence assignment.
- Standard Item engineering extension fields (`itag_*`).
- Possible-duplicate Item detection (`duplicate_service.py`).
- Engineering Item Request with a full approval workflow (Draft through Item Created/Closed, plus Rejected/Cancelled).
- Idempotent EIR-to-Item creation, gated on Approved state and resolved duplicates.
- 6 reports: EIR Register, Item Code Rule Register, Item Code Reservation Report, Possible Duplicate Item Report, Item Engineering Baseline, Items Missing Engineering Classification.

## Build ITAG-0.3.0 — Drawing, Specification, and Product Revision

- Technical Specification with a Critical Requirements child table.
- Engineering Drawing with a full release workflow (Draft through Released/Superseded/Obsolete), server-side immutability once Released, and automatic SHA-256 file-checksum computation on the approved attachment.
- Product Revision, which can only reference a Released Engineering Drawing, with its own release workflow and immutability.
- Drawing and Product Revision revision-creation, comparison, and effective-resolution services.
- 7 reports: Drawing Revision Register, Drawing Approval Aging, Missing Released Drawing File, Technical Specification Register, Product Revision History, Product Revision Comparison, Superseded and Obsolete Engineering Records.

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
