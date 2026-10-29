"""F3 (Waheed, 29-Oct-2026): Product Revision is submittable.

Runs after the DocType sync (post_model_sync), so is_submittable and the new
permission rows from product_revision.json are already in place. This patch
only:
- applies the same rights to any Custom DocPerm rows on Product Revision
  (Engineering User: no submit/cancel/amend/delete; Engineering Manager and
  Engineering Master Manager: submit/cancel/amend) and sets amended copies to
  take their normal {item}-PR-{revision_number} name;
- sets any active Workflow on Product Revision to inactive (kept, not
  deleted).

It changes no Product Revision record: every existing revision stays a draft
(docstatus 0) with its current revision_status/workflow_state, including
revisions already marked Released. Nothing is deleted.

Rollback: redeploy 15.5.7; set is_active = 1 on the workflow if wanted; reset
the Custom DocPerm flags in Role Permissions Manager.
"""

from itag_engineering.install import (
	apply_product_revision_submit_permissions,
	deactivate_product_revision_workflows,
)


def execute():
	deactivate_product_revision_workflows()
	apply_product_revision_submit_permissions()
