# Technical review — `feature/gap-fixes` (`15.5.14`)

Read-only review of the Frappe app `itag_engineering` at commit `45cfaaf` (branch `feature/gap-fixes`, `__version__ = "15.5.14"`). The app was inspected as reference material for a future ERPNext v15 app named ERPCloud Engineering. No product behavior was changed.

This is a static reading of the tree in this checkout. The suite was not executed and no bench was available, so nothing below depends on a live migrate or a Desk session. Line numbers refer to this commit.

Severity:

- **Critical** — wrong manufacturing data or a control that does not do what its own code says it does, on the path the app ships.
- **High** — data corruption, a site-wide production block, or an unauthenticated-role data leak. Confirmed from the source.
- **Medium** — real defect with a narrower trigger, or a control that is present but dead or racy.
- **Low** — limited impact, or a hazard that needs a specific caller.
- **Info** — structure, pins, and things the rebuild should copy on purpose.

---

## Critical

### C1. Multi-level BOM Builder never links a sub-assembly BOM

`ITAGBOMCreator.create_bom` (`itag_engineering/itag_engineering_management/bom_creator_override.py`) replaces ERPNext's `BOMCreator.create_bom` via `override_doctype_class` in `hooks.py`. It saves every generated BOM with `bom.save(ignore_permissions=True)` and does not submit it.

A parent row is given `bom_no` only when the child BOM already has `docstatus == 1`:

```56:70:itag_engineering/itag_engineering_management/bom_creator_override.py
		for item in production_item_wise_rm[(row.item_code, row.name)]["items"]:
			bom_no = ""
			item.do_not_explode = 1
			if (item.item_code, item.name) in production_item_wise_rm:
				sub_bom = production_item_wise_rm.get((item.item_code, item.name)).bom_no
				if sub_bom and frappe.db.get_value("BOM", sub_bom, "docstatus") == 1:
					bom_no = sub_bom
					item.do_not_explode = 0
			...
		bom.save(ignore_permissions=True)
```

The child was saved as a draft in the same run, so `docstatus` is 0, `bom_no` stays blank, and `do_not_explode` stays 1. The module docstring says the link is added when the sub-assembly is released. No other function writes `BOM Item.bom_no` after this. Submitting the child later does not update the parent row.

`ITAG BOM Workflow` is shipped inactive (`fixtures/workflow.json`, `"is_active": 0`, and `DEACTIVATED_WORKFLOWS` in `install.py`), so nothing in this app submits those drafts as part of the builder.

Effect: a multi-level BOM from the BOM Creator does not explode sub-assemblies. ERPNext treats those rows as leaf components. `save(ignore_permissions=True)` also creates the BOM even when the user has no BOM create right, as long as they can run BOM Creator.

---

## High

### H1. Every new Item overwrites `custom_product_type` from `itag_item_type`

`hooks.py` registers `fill_old_product_type_from_itag_item_type` on `Item.before_validate` for every Item, not only items created from an Engineering Item Request.

```107:120:itag_engineering/itag_engineering_management/item_type_options.py
def fill_old_product_type_from_itag_item_type(doc, method=None):
	...
	if doc.is_new() and not doc.get(NEW_ITEM_FIELD) and doc.meta.has_field(NEW_ITEM_FIELD):
		doc.set(NEW_ITEM_FIELD, "Critical")
	value = doc.get(NEW_ITEM_FIELD)
	field = doc.meta.get_field(ITEM_FIELD)
	if value and value in (field.options or "").split("\n"):
		doc.set(ITEM_FIELD, value)
```

`ITEM_FIELD` is `custom_product_type` (owned by `erpcloud_itagksa`, not by this app). `NEW_ITEM_FIELD` is `itag_item_type`, whose custom-field default is `Critical` (`setup/custom_fields.py`).

On a new Item, a blank `itag_item_type` is forced to `Critical`, and that value is written onto `custom_product_type` whenever it is one of the old field's options. A caller-supplied `custom_product_type` is discarded. The test locks that in:

```167:169:itag_engineering/tests/test_v15_5_14_item_type_field.py
	def test_new_item_old_field_follows_itag_item_type(self):
		item = self._new_item(itag_item_type="Non-Critical", custom_product_type="General")
		self.assertEqual(frappe.db.get_value("Item", item.name, "custom_product_type"), "Non-Critical")
```

The same assignment runs on every later save, so the two fields cannot diverge in the other direction either: editing `itag_item_type` replaces the erpcloud value. Which hook wins if `erpcloud_itagksa` also writes the field on `validate` depends on installed-app order. This app does not check that.

`after_migrate` also hides the erpcloud field (`hide_old_item_product_type` → Property Setter `hidden = 1`). Users then edit only `itag_item_type`, and every Item save pushes that value into the hidden mandatory field.

### H2. The Item Type copy touches every Item, and the tests call it

`copy_product_type_to_itag_item_type` loads every Item and `set_value`s `itag_item_type` whenever `custom_product_type` is `General`, `Critical`, `Non-Critical`, or `Non-Product`. It does not skip rows whose `itag_item_type` is already set. `General` becomes `Non-Product` on the new field only; the old field is left as `General` until a later save (H1 then changes it).

```83:87:itag_engineering/itag_engineering_management/item_type_options.py
	for name, old in frappe.get_all("Item", fields=["name", ITEM_FIELD], as_list=True):
		new = "Non-Product" if old == "General" else old
		if new in valid:
			frappe.db.set_value("Item", name, NEW_ITEM_FIELD, new, update_modified=False)
			changed[name] = new
```

The patch `patches/v15_5_14/copy_item_type_to_itag_item_type.py` calls this once from `patches.txt` (Frappe will not run it again on a normal migrate). The function itself is not "fill blanks only". `TestItagItemTypeCopyPatch` calls it directly (`tests/test_v15_5_14_item_type_field.py`, `test_copy_maps_values_and_general_to_non_product` and `test_idempotent`). `test_idempotent` only checks that a second full-table pass returns the same dict. That passes because the second pass writes the same values again, including over any `itag_item_type` a user changed after the first pass without a mirroring save.

Values outside that four-value set are skipped, so those Items keep a null `itag_item_type`. The Select has no blank option and the default is `Critical`. The next document save that stores `Critical` then hits H1 and replaces `custom_product_type`.

### H3. Work Order submit is blocked for every BOM, and the settings switches do not gate it

Two `Work Order.before_submit` hooks always run (`hooks.py`):

1. `block_work_order_unreleased_bom` throws unless some Engineering Release has `bom = doc.bom_no`, `release_status = "Released for Production"`, and `docstatus < 2`. There is no item, company, or "engineered item" filter. The matching `validate` warning returns early when `bom_no` is empty; the submit hook does not.
2. `freeze_baseline_before_submit` throws unless `resolve_effective_release` finds a release for `production_item` / `company`.

`Engineering Settings` exposes `engineering_release_enforcement` and `work_order_baseline_enforcement`. `engineering_settings.py` states that those flags, plus `traceability_enabled`, are informational and that nothing outside that file reads them. `eco_auto_hold_enabled` is the counter-example: `eco_auto_hold_service.py` actually reads it.

Installing the app on a normal ERPNext company blocks submit of every Work Order that has not been through this release path. Draft save is allowed (`warn_work_order_unreleased_bom`).

### H4. `search_similar_items_api` has no permission check

```72:75:itag_engineering/itag_engineering_management/duplicate_service.py
@frappe.whitelist()
def search_similar_items_api(**kwargs):
	results = find_possible_duplicates(**kwargs)
	return success(data={"results": results})
```

`find_possible_duplicates` uses `frappe.get_all("Item", ...)`, which does not apply user permissions. Any logged-in user can pass spec values and receive `item_code`, `item_name`, and the engineering spec fields. `allow_guest` is not set. Other whitelisted methods in this app generally check a role inside the service; this one does not.

### H5. Several tests delete or rewrite shared master data

These run as part of `bench run-tests --app itag_engineering` on whatever site the bench points at. The project's own notes say that site is a real development bench.

| Location | What it does |
|---|---|
| `doctype/valve_type/test_valve_type.py` `setUp` / `tearDown` | `frappe.db.delete("Valve Type", {"valve_type_code": "WEDGE"})` |
| `tests/test_uat_001_002.py` | `frappe.db.delete("Item", {"item_code": ["like", "CS-BALL-%"]})` |
| `tests/test_v15_5_14_item_type_field.py` | calls `copy_product_type_to_itag_item_type()` (every Item; see H2) |
| `tests/test_v15_5_12_next_build.py` `test_property_setter_survives_after_migrate_and_fixture_overwrite` | `frappe.db.delete("Property Setter", ... custom_product_type / options)` even when the test did not create that field |

`TestHandMadeItemSavesWithHiddenMandatoryOldField` does limit Item deletes to names it created, and it restores `reqd` in `try/finally`. The copy tests and the UAT / Valve Type deletes do not. `frappe.db.delete` on Item also leaves child rows behind; other tests in this app already comment on that (`test_fix8_item_request_submit.py`).

`WEDGE` and `CS-BALL-` are plausible real valve codes, not test-only prefixes.

---

## Medium

### M1. BOM release-control checks never run in the shipped configuration

`validate_release_control` and `guard_bom_submit` return immediately unless `is_enforced` is true. `is_enforced` is true only when the DocType has an active workflow, and it is also forced off when `frappe.flags.in_test` is set unless the test sets `frappe.flags.itag_enforce_release_control`.

`ITAG BOM Workflow` is `"is_active": 0` in `fixtures/workflow.json` and is deactivated again in `after_migrate` (`install.py`, `DEACTIVATED_WORKFLOWS`). `get_workflow("BOM")` is therefore empty, and the "creator cannot approve / approver cannot release / submit only from Approved" checks do not run.

`release_control.py` and `bom_creator_override.py` still describe that workflow as the path every BOM takes. `install.py` (fix6) is the later comment and says the workflow is kept inactive on purpose. Engineering User is denied BOM submit (`ENGINEERING_BOM_DENIED`); Engineering Manager is not, and can submit a draft BOM with no second person.

Engineering Release is different: `ITAG Engineering Release Workflow` is `"is_active": 1` and `workflow_state_field` is `workflow_state`. Those checks do run outside tests.

### M2. `itag_item_type` and the column break share one `insert_after`

```45:64:itag_engineering/setup/custom_fields.py
			{
				"fieldname": "itag_item_type",
				...
				"insert_after": "itag_engineering_item_request",
			},
			{
				"fieldname": "itag_column_break_1",
				"fieldtype": "Column Break",
				"insert_after": "itag_engineering_item_request",
			},
```

`sync_custom_fields` calls `create_custom_fields(..., update=True)` on every migrate, so this anchor is rewritten, not left as a one-time mistake. The column break was the original next field. Item Type was added with the same anchor instead of `insert_after: "itag_item_type"`.

The Engineering tab on BOM is anchored at the core field `column_break_oxbz` (`get_bom_fields`). That name is an ERPNext field id. If a v15 patch renames it, the tab's `insert_after` no longer points at a real field.

### M3. Item Type mirror is skipped when the new value is not an old option

`fill_old_product_type_from_itag_item_type` writes `custom_product_type` only when `itag_item_type` is in `(field.options or "").split("\n")`. If the Property Setter that adds `Critical` / `Non-Critical` / `Non-Product` has not run, or the stored value is not in that list, the hidden mandatory field is left unchanged and the two fields diverge with no error.

`ensure_item_product_type_options_and_default` runs from this app's `after_migrate`, after fixture sync. Another app's later `after_migrate` can still reset the Custom Field or the Property Setter. This repo cannot show `erpcloud_itagksa`'s hooks; the coupling is the Property Setter on a field this app does not own.

### M4. Stock Entry hold check labels almost every purpose as consumption

```134:142:itag_engineering/itag_engineering_management/hold_service.py
def block_stock_entry_transfer_or_consumption(doc, method=None):
	action = "Transfer Material" if doc.purpose == "Material Transfer for Manufacture" else "Consume Material"
	block_if_held(doc, action, {"Work Order": "work_order"})
	for row in doc.get("items") or []:
		if row.item_code:
			_raise_if_held("Item", row.item_code, action)
```

The hook is `Stock Entry.before_submit` with no `purpose` filter. Receipts, manufacture, repack, and material issues all use the action name `Consume Material`. A hold that blocks only that action also blocks a receipt of the same item. `place_hold` defaults `blocked_actions` to every action, so a default hold blocks the stock entry anyway; a hold narrowed to "Consume Material" does not mean what the label says.

The function comment says the purpose strings were not checked on a bench. The `else` branch is still visible in the source: only one purpose is special-cased.

### M5. Whitelisted writes are role-gated, then saved with `ignore_permissions`

The usual pattern (EIR item create, hold place/release, WIP link, ECO create, impact-analysis insert) checks that the session has one of a fixed role tuple, then `insert` / `save(ignore_permissions=True)`. It does not call `check_permission` on the target document.

Consequences that are visible in the code:

- An Engineering User / Manager / Master Manager can `create_item_from_eir` for a submitted request they can read, and the Item is inserted without Item create permission (`eir_service.py`).
- `run_duplicate_check` updates `possible_duplicates_json` with `db.set_value` after a role check. `get_doc` still enforces read.
- `place_hold(**fields)` builds the hold from the request body. The role check is `Engineering Manager` only. Fields are not allow-listed beyond what the DocType controller validates.
- `make_engineering_drawing` / `make_bom` (`item_request_links.py`) check read on the request and not create on the target. `drawing_links.py` does check create. The mapper returns an unsaved document; the later insert is a separate permission check.
- `get_open_count` is replaced globally (`override_whitelisted_methods`). For an Engineering Item Request it then `frappe.db.count`s Product Revision and Engineering Release by item, with no `docstatus` filter and without the Engineering Release permission query in `permission_service.py`.

`preview_item_code_api` uses `frappe.get_doc("Item Code Rule", ...)`, so read permission on that DocType applies. `ping` is intentionally open to any logged-in user.

### M6. Engineering Release comments describe a workflow the fixture does not have

`engineering_release.py` (module comment) and the first half of `engineering_release.js` `refresh` say `release_status` is the workflow state field and that the DocType has no `workflow_state`. The DocType JSON has both fields. `fixtures/workflow.json` for `ITAG Engineering Release Workflow` sets `workflow_state_field` to `workflow_state` and the states Draft → Approved → Released. There is no transition whose next state is `Released for Production`.

`submit_engineering_release` sets `release.release_status = "Released for Production"` and `save()`s. Its comment says that save depends on a workflow edge to `Released for Production`. The active workflow does not watch `release_status`, so that save is not a workflow transition today. The v15.5.13 F4 button correctly checks `workflow_state === "Released"` (`engineering_release.js` and `_check_release_for_production_allowed`).

The current fixture and the F4 check agree with each other. The Python module comment and the comment inside `submit_engineering_release` do not. Pointing `workflow_state_field` back at `release_status` to match those comments would make `release.save()` subject to workflow transition checks that the fixture does not define.

`POST_RELEASE_ALLOWED_FIELDS` is `release_status`, `modified`, `modified_by`. It does not include `workflow_state`. After `release_status` is already a released state, a later workflow change is rejected by `validate_immutable_once_released`. The transition into `Released for Production` is allowed because the check looks at the previous status.

Superseding the previous release is a `db.set_value` of `release_status` to `Superseded` (`release_service.py`). That bypasses the immutability check and does not change `workflow_state`.

### M7. One active Drawing / BOM per request is not enforced in the database

`validate_one_per_request` and `_assert_can_create` (`item_request_links.py`) `get_all` an existing non-cancelled row and then throw. Two concurrent saves can both see no row. `BOM.itag_item_request` is a custom Link with `search_index` only (`get_item_request_link_fields`). There is no unique index.

### M8. Release-control coverage is off unless a test opts in

`is_enforced` returns false for the whole test run unless `frappe.flags.itag_enforce_release_control` is set (`release_control.py`). Tests that submit a BOM or a Work Order without that flag do not exercise the production branch of `guard_bom_submit`, `validate_release_control`, or the F4 branch of `submit_engineering_release` (`_f4_enforced` uses the same helper). `test_release_control.py` is the suite that turns the flag on. The gap is the rest of the UAT tests, which keep working because the flag defaults off.

---

## Low

### L1. Cancel-blocked message builds HTML from document names without escaping

`disable_item_for_eir` (`eir_service.py`) puts `frappe.bold(item_code)` and `frappe.bold(n)` inside a `<ul>` passed to `frappe.throw`. `public/js/bom.js` escapes readiness exception text with `frappe.utils.escape_html` before putting it in HTML. The server message does not. Document names are mostly series-generated; an Item code or Work Order name that contains markup is not escaped here.

### L2. Permission query is one default company, not User Permissions

`permission_service.py` hides Engineering Release, Change Impact Assessment, Engineering Approval Matrix, and Item Code Rule rows whose `company` is set and is not Engineering Settings' `default_company`. Blank `company` stays visible. Administrator and System Manager bypass it. The company value is passed through `frappe.db.escape`. Under the single-company rule this is unused filtering; it does not follow ERPNext User Permissions, and a wrong Default Company hides the rows from every other user.

### L3. Raw SQL updates use constant identifiers

`item_type_options.py` (`rename_general_to_non_product`, `items_general_to_non_product`), `patches/v15_5_6/set_initial_workflow_states.py`, and `patches/field_conversion_utils.py` interpolate DocType or field names into SQL. The names in this tree are literals (`custom_product_type`, `BOM`, and the placeholder field list), not request input. `install.py` `remove_retired_engineering_roles` passes the role as `%s`. No request-shaped SQL injection showed up in app code.

The Item and Engineering Item Request updates do not go through `validate`, do not bump `modified`, and the EIR update does not care about `docstatus`. They are one-shot patches and they no-op when nothing is `General`. Re-running the Python function is safe in the sense that a second pass finds no `General` rows; it is not wrapped in `try/finally` because it does not hold a temporary schema change.

### L4. `BOM.itag_product_revision` is written with `set_value` and is not `allow_on_submit`

`ProductRevision.link_bom_to_revision` (`product_revision.py`) sets the link on submit with `update_modified=False`. `get_bom_fields` does not set `allow_on_submit` on `itag_product_revision`. The write succeeds because `set_value` skips Document validation. A later BOM `save()` of that submitted document cannot change the field through the normal API. The audit log row is the record of the change.

### L5. `block_work_order_unreleased_bom` does not treat a blank `bom_no` as "nothing to check"

The validate warning returns when `bom_no` is empty. The submit hook calls `released_engineering_release_for_bom(None)`, which returns `None`, and then throws. Tests in this repo state that ERPNext marks `Work Order.bom_no` mandatory, so a normal document should not reach submit with it empty. The two hooks are still inconsistent.

### L6. Job Card status strings are asserted in code and marked unverified in comments

`hooks.py` and `hold_service.block_job_card_start` / `block_job_card_operation_completion` fire only when `status` changes to `Work In Progress` or `Completed`. The comments say that was not confirmed against `Job Card` meta on a bench. This review did not have a bench either, so this is an unverified coupling, not a demonstrated mismatch.

---

## Info

### Structure and version pins

- One module, `ITAG Engineering Management` (`modules.txt`). About 43 DocType JSON files under `itag_engineering/itag_engineering_management/doctype/`, including child tables. Package version is only `__version__` in `itag_engineering/__init__.py` (`15.5.14`). `pyproject.toml` uses flit, `requires-python >= 3.10`, and `[tool.bench.frappe-dependencies] frappe = ">=15.0.0,<16.0.0"`. There is no ERPNext pin. `hooks.py` `required_apps = ["erpnext"]` does not constrain the ERPNext minor version.
- No `setup.py`. That matches a flit app. No checked-in core copies of `frappe/` or `erpnext/`.
- Extension points that are supported hooks, not file edits: `doc_events` on Item, BOM, Engineering Release, ECO, Work Order, Job Card, Stock Entry, Quality Inspection, Delivery Note, Production Engineering Hold; `doctype_js` for BOM; `override_doctype_class` for BOM Creator; `override_whitelisted_methods` for `frappe.desk.notifications.get_open_count`; `permission_query_conditions` for four DocTypes; fixtures for Workflow, Dashboard Chart, Number Card, Dashboard.
- `patches.txt` has a real `pre_model_sync` entry (`v15_5_7.seed_item_request_dropdown_masters`) and post-model patches through `v15_5_14.copy_item_type_to_itag_item_type`. The v15.5.12 / v15.5.13 / v15.5.14 item-type patches call the helpers above. They do not `delete_doc` business records. `remove_retired_engineering_roles` and `remove_engineering_workflows` disable records and log leftovers.
- `before_migrate` creates roles so DocType sync can attach permissions. `after_migrate` re-applies roles, deactivates retired workflows, syncs custom fields, and reapplies the Item Type options / hide setter last in this app's hook list.
- Workflow fixture `is_active` matches the deactivate list for the BOM workflow (both off). Engineering Release, ECR, and ECO ITAG workflows are active in the fixture.
- Scheduler: hourly impact-staleness sweep, daily deviation expiry. No second scheduler path was reviewed line by line.
- Secrets: no private keys or API tokens in the tree. `pyproject.toml` has the publisher email `waheed@globcomqatar.com`. `.github/workflows/ci.yml` uses the local bench passwords `root` / `admin`.
- `compatibility_mode` still exists and defaults so `is_v15()` keeps working; the Desk hides it (described in the repo status notes). This app is v15-only in comments and in the Frappe pin.
- Child tables have empty permission lists, which is normal. Engineering Settings is a Single.

### What the gap-fixes commits actually changed

From `5836ad5` through `45cfaaf` (v15.5.14, including the item-type follow-ups):

- Work Order warning on save and hard stop on submit (H3). BOM cancel is refused while an Engineering Release for that BOM is `Released for Production` or `Suspended` (`guard_bom_cancel`). That cancel guard does not depend on the inactive BOM workflow.
- Product Revision submit writes `BOM.itag_product_revision` when the field is blank, and refuses the link when another non-cancelled revision already holds it (L4). Supersession checks same Item, same Company, and `Released for Production` (`validate_superseded_release`), and that check is skipped once this release is already `Released for Production`.
- Item codes: `sync_item_code_with_naming_rule` copies `name` into `item_code` only on insert (`flags.in_insert`), only when `item_code != name`, and only when `matching_document_naming_rule` finds an enabled Document Naming Rule whose conditions match. Naming-series and typed codes are left alone when no rule matches. The hook order comment matches Frappe's `set_new_name` (naming rule before `Item.autoname`, then `before_validate`).
- Item Type build 2: own field `itag_item_type`, copy patch, hide `custom_product_type`, mirror on every Item save (H1, H2, M2, M3). The `reqd` restore in `TestHandMadeItemSavesWithHiddenMandatoryOldField` is in `try/finally`. The copy helper and the other tests were not narrowed to the rows they created (H2, H5).

### Tests

There is broad UAT and per-fix coverage (item request submit/amend/cancel, duplicate rules, release F4, product revision submit, permissions). The holes that matter are the ones above: release control is opt-in during tests (M8), the item-type copy and a few cleanups are not scoped to fixtures (H5), and nothing in the BOM Creator override tests can pass a multi-level case where the child BOM is still draft — the production code never sets `bom_no` in that case (C1).

---

## Suitability as a reference for ERPCloud Engineering

Keep the domain model and the rules that are actually implemented as DocType controllers plus small services: Engineering Item Request submit creates or re-enables one Item and cancel disables it without deleting; duplicate detection that requires several identity fields; item-code reservation by a unique `Item Code Reservation.item_code` and a retry loop; Document Naming Rule glue that only rewrites `item_code` when a rule matched; Engineering Release as its own document with a checksum, approval steps, and an explicit "submit for production" server method; holds that name the blocked action; product-revision submit/cancel/amend; and permission changes made through `add_permission` / Custom DocPerm rather than by editing ERPNext files. Copy the shape of `eco_auto_hold_enabled` (a setting the service reads) and do not copy the release and baseline checkboxes, which the settings controller already documents as unread. Rewrite BOM Creator integration against the current ERPNext `create_bom` instead of keeping this subclass: the override drops sub-assembly links and saves with `ignore_permissions`. Do not carry the dual-write onto `Item.custom_product_type` or a Property Setter that hides another app's field; give ERPCloud Engineering one Item Type field and migrate data into it once, only where the target is blank. Gate Work Order, Stock Entry, Delivery Note, and Job Card hooks on an explicit per-item or per-company flag so a normal ERPNext company can submit work that is not in the engineering baseline. Replace role-only `ignore_permissions` writes with `check_permission` on the document, and do not ship a whitelist that uses `get_all` on Item with no role check. Treat `feature/gap-fixes` as a catalog of the valve workflow and of bugs already paid for (workflow field vs status field, inactive BOM workflow vs comments that still describe it, tests that delete `WEDGE` and `CS-BALL-%`), not as a tree to port forward.
