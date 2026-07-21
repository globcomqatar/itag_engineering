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
`main` (renamed from `develop`; `main` is the GitHub default branch). Decision Log:
`doc/ITAG_Decisions.md` (bench root). Per-build implementation plans:
`docs/superpowers/plans/` (one file per build, `2026-MM-DD-build-X.Y.Z-<slug>.md`).

**Versioning scheme (MAJOR.MINOR.PATCH), set in `itag_engineering/__init__.py`'s `__version__`
(flit reads it from there via `pyproject.toml`'s `dynamic = ["version"]` — this is the only
place the version lives, nowhere else needs a manual bump):** MAJOR tracks the Frappe framework
version this app targets (`15`); MINOR increments for a big change — a new feature, a new build
going live, anything that changes what the app *does*; PATCH increments for a small
change/fix that doesn't add new capability. Current: `15.2.0`, marking Builds ITAG-0.1.0 through
ITAG-0.11.0 complete and independently verified against the real bench, plus the standalone
"ITAG Engineering" Dashboard (9 charts, 6 number cards) added on top. Next big change (e.g.
Build ITAG-1.0.0 actually going live) → `15.3.0`; a small fix in between → `15.2.1`, `15.2.2`, ...
**Every change to this app bumps the version as part of that same change — don't leave it for
later.** Tag the release on GitHub to match (`git tag v15.1.0`, pushed alongside the commit).

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

## Standing rule: every new DocType gets a Desk Workspace entry

This app has one Desk Workspace, `ITAG Engineering` (module-owned under the "ITAG Engineering
Management" module — the workspace's own name/label was shortened from "ITAG Engineering
Management" to "ITAG Engineering"; the underlying module name is unchanged, exported at
`itag_engineering/itag_engineering_management/workspace/itag_engineering/itag_engineering.json`).
It follows the same **two-tier structure every standard Frappe/ERPNext workspace uses**
(compare `erpnext/selling/workspace/selling/selling.json` or `.../manufacturing/manufacturing.json`):

1. **Quick Access** (top) — a SMALL curated row of `shortcuts` (the `Workspace Shortcut` child
   table + matching `"shortcut"` content blocks), one flagship/entry-point DocType per build
   phase, not the full list. This is a launcher, not an index.
2. **Reports & Masters** (bottom) — the COMPREHENSIVE, one-entry-per-DocType listing, via the
   `links` child table (`Card Break` rows grouping `Link` rows) and matching `"card"` content
   blocks, one card per build-phase group.

**Every DocType any future build/phase adds to this app (excluding child tables and the
Engineering Settings Single) must get a `Link` row under the correct Reports & Masters group —
this is the mandatory, comprehensive part.** Only add it to Quick Access too if it's genuinely
a primary entry point for that phase's workflow (most new DocTypes should NOT go in Quick
Access — it stays small by design).

**Every new build/phase's REPORTS need a home in Reports & Masters too, not just its
DocTypes** — this was a second real gap found after the first fix: an entire build's worth of
reports (Build 0.4.0's 7 BOM/Routing/Inspection reports) had no card anywhere in the workspace,
and every existing card only ever listed `link_type: "DocType"` rows, never `link_type:
"Report"` rows, despite the section being named "Reports & Masters." A build that adds no new
DocType of its own (like 0.4.0) still needs its own Card Break group, populated with Report
links only. For a build that does add DocTypes, include at least one or two representative
Report links (`"type": "Link", "link_to": <report name>, "link_type": "Report", "is_query_report": 1`)
alongside the DocType links in the same card, matching standard ERPNext workspaces (e.g.
Manufacturing mixes `link_type: "DocType"` and Report links in the same cards) — don't rely on
DocType links alone to satisfy "this build is represented in the workspace."

**A chart is optional but welcome** (matches the pattern of ERPNext's own workspaces, e.g.
Selling's "Sales Order Trends") — a `Dashboard Chart` record (`chart_type: "Group By"`,
`document_type`, `group_by_based_on` a Select/Link field on that doctype, `type: "Donut"`/`"Bar"`/etc.,
`is_public: 1`) referenced by a `"chart"` content block (`{"type": "chart", "data": {"chart_name": ..., "col": 12}}`)
placed right after the title header. Showing "No Data" until real records exist is expected and fine.

**Do not let the two sections duplicate each other's full content** — this exact mistake
happened once already while building this workspace: every DocType was placed in BOTH the
shortcuts row AND the Reports & Masters cards, so each one rendered twice on the page. A
handful of intentional overlaps between the two sections is normal and matches Frappe's own
convention (e.g. ERPNext's Selling workspace lists "Item" in both Quick Access and Items and
Pricing) — but Quick Access must stay a curated subset, never a mirror of the full list.

**How to update it correctly — the same mechanism Frappe uses for DocTypes themselves, never a
hand-edited JSON file:**

1. Confirm `developer_mode: 1` is set in the site config (`sites/frappedevelopment.localhost/site_config.json`) — this workspace's `on_update()` hook only auto-exports to a file when it is.
2. Load the real document — `frappe.get_doc("Workspace", "ITAG Engineering")` — via a `bench execute` script (a throwaway module under `itag_engineering/`, e.g. `_scratch_probe.py`; delete it after use, it is not meant to be committed).
3. Append the `Link` row (`{"type": "Link", "label": <DocType>, "link_to": <DocType>, "link_type": "DocType", ...}`) to `doc.links`, either under an existing group's `Card Break` (bump its `link_count`) or under a new `Card Break` for a new build phase, plus the matching `"card"` block in `content` if it's a new group. Only also append a `shortcuts` row + `"shortcut"` content block if this DocType is a deliberate Quick Access addition (see above). **Always use `doc.append("links"/"shortcuts"/"charts", {...})` for every child-table row — never assign a plain list of dicts directly (`doc.charts = [{...}]`)**, which crashes with `AttributeError: 'dict' object has no attribute 'is_new'` deep inside Frappe's `_set_defaults()` the moment you call `.save()`, since Frappe expects real BaseDocument-wrapped rows, not bare dicts.
4. Call `doc.save()` — with `developer_mode` on and the workspace `public: 1`, this **automatically re-exports the JSON file** (Frappe prints `Wrote document file for Workspace ... at <path>` when it does). Confirm that message appears; if it doesn't, something is wrong with the `developer_mode`/`public` precondition, not the save itself.
5. Never hand-edit `itag_engineering_management.json` directly — the same rule this app already applies to DocType JSON files applies here (they are Frappe-generated exports, not something to author by hand), and a hand edit will look subtly different from what Frappe itself produces (key ordering, escaping) the next time a real save happens, creating a noisy diff.
6. Run `bench migrate` once afterward to confirm the change is stable and doesn't get reverted or duplicated on a normal migrate cycle.
7. Actually look at the rendered workspace in the Desk (or a screenshot) before considering the change done — the duplication bug above was only caught by looking at the page, not by reading the JSON.
