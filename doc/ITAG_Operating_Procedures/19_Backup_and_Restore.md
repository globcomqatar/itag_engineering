# Operating Procedure: Backup and Restore

**Roadmap:** Section 24.5 item 19 / Section 24.7 checklist ("backup completed/verified", "restore verified"). **Build:** none — this app adds no custom backup mechanism; it relies entirely on standard Frappe/`bench` tooling.

## What's actually built
Nothing custom. `itag_engineering` stores all of its data as ordinary Frappe DocTypes in the site's own MariaDB database and its attached files (Engineering Drawing's approved files, etc.) in the site's standard `private`/`public` files directories — both are already covered by Frappe's own `bench backup --with-files` mechanism with no special handling required.

## Procedure
1. Use the site's standard backup schedule (`bench backup --with-files`, typically scheduled via cron on the actual Production host — confirm the real schedule with the IT/ERPNext Owner, since this program has never operated a live site).
2. Before any Production cutover or major migration action, take a manual, verified backup and confirm the backup file's integrity (e.g. a test restore to a scratch site) — this is explicitly required by the Cutover Readiness Checklist's "backup completed/verified" and "restore verified" line items, and must be genuinely executed, not assumed.
3. To restore: `bench --site <site> restore <backup-file> --with-private-files --with-public-files`, then `bench migrate` to bring the schema current if the backup predates a later `itag_engineering` release.
4. After ANY restore, re-run the **Permission Exception Report** and **Segregation of Duties Conflict** report before returning the site to service — a restored backup could reflect an older, since-fixed permission state.

## Escalation
This program has never operated a live site, so no restore has ever actually been exercised end-to-end for `itag_engineering` specifically. Treat the FIRST real restore rehearsal as a genuine test, not a formality — confirm every DocType, Workflow, Role, and Custom Field this app defines survives the restore intact before relying on this procedure operationally.
