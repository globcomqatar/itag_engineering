# ITAG Engineering Management (`itag_engineering`)

Engineering Management and Product Lifecycle control layer for ERPNext Manufacturing (valve
manufacturing), built against `ITAG_Engineering_Management_Master_Roadmap_v1.0(Approved).md`.

## Current status

Builds ITAG-0.1.0 through ITAG-0.11.0 are implemented, migrated, and independently verified
against the real bench (`frappedevelopment.localhost` inside `frappe-docker_devcontainer-frappe-1`):
`bench migrate` runs clean and idempotent, and the full app suite passes 394/394 with zero
failures/errors (`bench --site frappedevelopment.localhost run-tests --app itag_engineering
--skip-test-records`). Build ITAG-1.0.0 (Production Release and Certification) is drafted per
its own plan but is mostly non-code deliverables (final regression evidence, operating
procedures, training materials, cutover checklist, production certification sign-off) that
require real human action — do not treat any of those as complete until the actual named
human approvers have signed off; an agent facilitates that build, it cannot substitute for it.

The repo lives at `https://github.com/globcomqatar/itag_engineering` (private), branch
`develop`. Decision Log: `doc/ITAG_Decisions.md` (bench root). Per-build implementation plans:
`docs/superpowers/plans/` (one file per build, `2026-MM-DD-build-X.Y.Z-<slug>.md`).

**Always run tests with `--skip-test-records`** — this bench's ERPNext install has no
`payments` app, so Frappe's default test-record dependency auto-resolution chains into a
nonexistent `Payment Gateway` DocType and crashes `bench run-tests` entirely. This app never
relies on Frappe's auto-generated `test_records` (every test builds its own fixtures via
`itag_engineering/tests/factories.py`), so this flag is always safe to use.

**Never run two `bench` commands against this site concurrently.** They share one MySQL
database; overlapping `bench run-tests`/`bench migrate` invocations have caused real deadlocks
(`pymysql.err.OperationalError: 1213`) that produce dozens of false-positive test failures.
Check `ps aux | grep bench` before starting a run if there's any doubt one might still be live.

## Development workflow — follow this for any future work in this app

1. **Plan** each build in detail before implementing (see `docs/superpowers/plans/` for the
   established format: Objective, Architecture, Global Constraints, File Structure, per-task
   TDD steps, Test Checkpoint, Exit Gate) — using the `subagent-driven-development` skill.
2. **Implement** task-by-task: a fresh implementer subagent per task, writing the failing test
   first, then the code, against the live bench.
3. **Review independently**: a fresh reviewer subagent (no memory of the implementation)
   re-verifies every claim live rather than trusting the implementer's report — this has
   caught real bugs in nearly every task across every build so far (workflow-state/mirror-field
   desync, permission checks gated only on the API wrapper and not the underlying service,
   child-table immutability gaps, `frappe.db.set_value` bumping `modified` and causing spurious
   `TimestampMismatchError`s, naive positional diffing, test-fixture collisions with real
   ERPNext demo data, and more). Fix-and-re-review any Critical/Important finding.
4. **Final whole-branch review** once every task in a build is done, before merging — this has
   independently caught cross-task issues no single task's review was scoped to find.
5. **One build at a time** in the dependency order the roadmap specifies — do not write a
   later build's detailed plan (beyond the forward-reference placeholders already established)
   until the prior build's real schema exists and is merged, unless explicitly asked to plan
   ahead without implementing (as happened for Builds 0.5.0-1.0.0's plans).
6. **A build plan written without a live bench available is a design, not verified fact.** If
   a build's code was ever written or planned without running it against the real bench (this
   happened for Builds 0.5.0-1.0.0, drafted in a session with no bench access), it MUST go
   through a real fix-and-verify pass against the live bench before being trusted — expect real
   bugs (ERPNext core mandatory fields silently omitted from test fixtures, Frappe API
   behaviors that don't work the way a comment assumed, etc.) that only running it can surface.

## Standing rule: every new DocType gets a Desk Workspace shortcut

This app has one Desk Workspace, `ITAG Engineering Management` (module-owned, exported at
`itag_engineering/itag_engineering_management/workspace/itag_engineering_management/itag_engineering_management.json`).

**Every DocType any future build/phase adds to this app (excluding child tables and the
Engineering Settings Single, which already has its own shortcut) must get a shortcut added to
this same workspace before that build is considered done** — do not let this drift the way it
did across Builds 0.1.0-0.11.0, where the workspace stub existed with an empty `shortcuts`
array the entire time until an explicit pass filled it in retroactively for all 21 DocTypes.

**How to do this correctly — the same mechanism Frappe uses for DocTypes themselves, never a
hand-edited JSON file:**

1. Confirm `developer_mode: 1` is set in the site config (`sites/frappedevelopment.localhost/site_config.json`) — this workspace's `on_update()` hook only auto-exports to a file when it is.
2. Load the real document — `frappe.get_doc("Workspace", "ITAG Engineering Management")` — via a `bench execute` script (see `itag_engineering/_scratch_probe.py`-style throwaway module used to build this workspace originally; delete the scratch file after use, it is not meant to be committed).
3. Append a `shortcuts` child row (`{"label": <DocType>, "link_to": <DocType>, "type": "DocType", "doc_view": "List", "color": "Grey"}`) and a matching `links` Card Break/Link pair under the correct build-phase group (add a new Card Break group for a new build phase, or append to an existing group's `link_count`/rows if the DocType belongs there).
4. Add a `"shortcut"` block referencing the same `shortcut_name` (and, if it's a new group, a `"header"` block) to the `content` JSON block list, matching the existing blocks' shape.
5. Call `doc.save()` — with `developer_mode` on and the workspace `public: 1`, this **automatically re-exports the JSON file** (Frappe prints `Wrote document file for Workspace ... at <path>` when it does). Confirm that message appears; if it doesn't, something is wrong with the `developer_mode`/`public` precondition, not the save itself.
6. Never hand-edit `itag_engineering_management.json` directly — the same rule this app already applies to DocType JSON files applies here (they are Frappe-generated exports, not something to author by hand), and a hand edit will look subtly different from what Frappe itself produces (key ordering, escaping) the next time a real save happens, creating a noisy diff.
7. Run `bench migrate` once afterward to confirm the change is stable and doesn't get reverted or duplicated on a normal migrate cycle.

Reference for structure/conventions: any standard ERPNext workspace, e.g.
`erpnext/manufacturing/workspace/manufacturing/manufacturing.json` — same `shortcuts`/`links`
(Card Break + Link)/`content` (JSON-stringified block list) shape this app's workspace follows.
