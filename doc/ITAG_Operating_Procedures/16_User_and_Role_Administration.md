# Operating Procedure: User and Role Administration

**Roadmap:** Section 24.5 item 16 / Decision Log #4 (16-role list), Section 22.3. **Build:** ITAG-0.1.0 (roles), ITAG-0.11.0 Task 1 (audit/segregation).

## What's actually built
- `install.py` — `create_roles()` creates every Role this app references, including `Production Manager` and `ITAG Integration User` (both added in ITAG-0.11.0). Wired into BOTH `after_install` (fresh installs) and `after_migrate` (so a Role a later build's DocType JSON references gets created on `bench migrate` even on an already-installed site) — a real gap this build's own audit found and fixed (`Production Manager` was referenced by 19 files but never created).
- `ITAG Integration User` is a role that must be able to do NOTHING approval/release-shaped — a structural "proving the negative" role. Do not grant it any DocPerm write/submit/cancel/delete beyond what integration endpoints genuinely need, and do not add it to any Workflow Transition's `allowed` list. The **Permission Exception Report** re-checks this live, every time it's run.
- `permission_service.py` — company-scoped `permission_query_conditions` for Engineering Release, Change Impact Assessment, Engineering Approval Matrix, Item Code Rule, reading the active company dynamically from Engineering Settings (a no-op under this program's single-company scope, but structurally ready for multi-company).
- Administrator is exempt from every segregation-of-duties guard in this app (the break-glass account) — this is intentional, not a bypass, and is required precisely so Administrator is never accidentally locked out.

## Procedure
1. Assign users to Roles per Decision Log #4's 16-role list — never invent a new role ad hoc; if a genuinely new role is needed, that's a change-control decision (roadmap §33), not an administrative action.
2. After creating a new user, confirm their assigned roles actually match their real job function using the **Permission Exception Report** and **Segregation of Duties Conflict** report — both are live, re-runnable checks, not one-time assertions.
3. Never grant `ITAG Integration User` any role capability beyond what a specific, named integration genuinely requires — re-run **Permission Exception Report** after any change to this role's permissions.
4. On every `bench migrate`, confirm `create_roles()` ran (it's wired into `after_migrate`) so any newly-referenced Role from a later build is present.

## Escalation
If **Permission Exception Report** or **Segregation of Duties Conflict** surfaces a real finding, treat it with the same severity Build ITAG-0.11.0's own audit did — escalate to the ITAG Engineering Administrator / IT-ERPNext Owner before it reaches Production.
