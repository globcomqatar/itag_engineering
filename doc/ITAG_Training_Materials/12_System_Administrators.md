# Training: System Administrators

**Role:** System Manager, ITAG Engineering Administrator, Administrator.

## What you do in this system
You own installation, roles, permissions, and technical health — the only roles that can write to `Engineering Audit Log` (System Manager) or hold every operational capability across the whole app (ITAG Engineering Administrator).

## What you'll actually use
1. **`bench migrate`** — `install.py`'s `create_roles()` runs on both `after_install` and `after_migrate`; confirm all Roles (including `Production Manager`/`ITAG Integration User`, added in ITAG-0.11.0) exist after every migrate.
2. **`health_check_api()`** (System Manager only) — app version, installed apps, and whether all 6 Workflows are `is_active`.
3. **Permission Exception Report**, **Segregation of Duties Conflict**, **Background Job Failure Report**, **Integration Failure Report** — your primary operational dashboards.
4. **`ITAG Integration User`** — never grant this role any capability beyond what a specific, named integration genuinely requires; re-check with **Permission Exception Report** after any permission change.
5. Administrator is the one identity exempt from every segregation-of-duties guard in this app (drawing creator/releaser, etc.) — a deliberate break-glass exception, not a bug; do not rely on it for routine work.

## What you will NOT be able to do (by design)
- Nothing is technically restricted for System Manager/Administrator — but every action you take as Administrator bypasses this app's own segregation-of-duties guards, so use it sparingly and only when genuinely necessary.

## Where to check status
**Permission Exception Report**, **Segregation of Duties Conflict**, **Background Job Failure Report**, **Integration Failure Report**, `health_check_api()`.
