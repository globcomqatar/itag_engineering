# Operating Procedure: Integration Failure

**Roadmap:** Section 24.5 item 18 / Section 22.5. **Build:** ITAG-0.11.0 Task 4-5.

## What's actually built
- `observability_service.get_integration_log(status=None)` reads Frappe's own `Integration Request` doctype (a genuine SQL-backed core doctype, unlike `RQ Job`).
- Report: **Integration Failure Report** — a thin wrapper filtering `get_integration_log()` to `status="Failed"`, always the live view.
- This application does not currently define any of its OWN outbound integrations (no external API calls are made anywhere in `itag_engineering`'s service layer as of ITAG-0.11.0) — every row in this report today would come from ERPNext core or any other installed app's own integration usage on this site, not from this app itself.

## Procedure
1. Check **Integration Failure Report** for any `Failed` row.
2. Read the row's `error` field for the actual failure reason and `integration_request_service` to identify which integration is affected.
3. Since this app defines no integrations of its own yet, escalate any finding here to the IT/ERPNext Owner as a site-wide (not `itag_engineering`-specific) issue, unless and until a future build adds a real outbound integration to this app.

## Escalation
If a future change adds a genuine `itag_engineering`-owned integration, this procedure must be revised to name that integration specifically and describe its own retry/backoff behavior — do not assume this generic procedure covers it without updating this document first.
