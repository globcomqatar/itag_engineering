"""fix8 (Waheed, 29-Oct-2026): Engineering Item Request is submittable with
no workflow. Submit creates the ERPNext Item; Cancel disables it.

Runs after the DocType sync, so is_submittable and the permission rows from
engineering_item_request.json are already in place. This patch only:
- sets any active Workflow on Engineering Item Request inactive (kept);
- applies the submit rights to any Custom DocPerm rows on the DocType.

No Engineering Item Request is changed: every existing request stays a
draft (docstatus 0) with its workflow_state, and requests already at
"Item Created" keep their created_item link. Nothing is deleted.

Rollback: redeploy 15.5.8; set is_active = 1 on the workflow if wanted.
"""

from itag_engineering.install import (
	apply_item_request_submit_permissions,
	deactivate_item_request_workflows,
)


def execute():
	deactivate_item_request_workflows()
	apply_item_request_submit_permissions()
