"""Product Revision effective-resolution, supersession, and comparison
service (roadmap Section 11.8)."""

import frappe
from frappe import _
from frappe.utils import today

BOOKKEEPING_FIELDS = {
	"name",
	"owner",
	"creation",
	"modified",
	"modified_by",
	"idx",
	"docstatus",
	"workflow_state",
	"revision_status",
	"revision_number",
	"previous_revision",
	"superseding_revision",
}


def retrieve_current_effective_product_revision(item):
	rows = frappe.get_all(
		"Product Revision",
		filters={
			"item": item,
			"revision_status": "Released",
			"effective_from": ["<=", today()],
		},
		fields=["name"],
		order_by="effective_from desc",
		limit=1,
	)
	if not rows:
		return None
	return frappe.get_doc("Product Revision", rows[0].name).as_dict()


def supersede_revision(old_revision_name, new_revision_name):
	if not frappe.db.exists("Product Revision", old_revision_name):
		frappe.throw(_("Product Revision {0} does not exist.").format(old_revision_name))
	if not frappe.db.exists("Product Revision", new_revision_name):
		frappe.throw(_("Product Revision {0} does not exist.").format(new_revision_name))

	frappe.db.set_value(
		"Product Revision",
		old_revision_name,
		{"superseding_revision": new_revision_name, "workflow_state": "Superseded", "revision_status": "Superseded"},
	)
	if not frappe.db.get_value("Product Revision", new_revision_name, "previous_revision"):
		frappe.db.set_value("Product Revision", new_revision_name, "previous_revision", old_revision_name)


def compare_product_revisions(item, revision_number_a, revision_number_b):
	name_a = f"{item}-PR-{revision_number_a}"
	name_b = f"{item}-PR-{revision_number_b}"
	doc_a = frappe.get_doc("Product Revision", name_a).as_dict()
	doc_b = frappe.get_doc("Product Revision", name_b).as_dict()

	diff = {}
	for fieldname in doc_b:
		if fieldname in BOOKKEEPING_FIELDS:
			continue
		if doc_a.get(fieldname) != doc_b.get(fieldname):
			diff[fieldname] = {"from": doc_a.get(fieldname), "to": doc_b.get(fieldname)}
	return diff
