"""Drawing revision creation and comparison service (roadmap Section 11.8)."""

import frappe
from frappe import _

from itag_engineering.itag_engineering_management.audit_service import log_audit_event

BOOKKEEPING_FIELDS = {
	"name",
	"owner",
	"creation",
	"modified",
	"modified_by",
	"idx",
	"docstatus",
	"workflow_state",
	"release_status",
	"drawing_revision",
	"file_checksum",
	"approved_file",
	"revision_date",
	"effective_date",
	"superseded_date",
}

CARRY_FORWARD_FIELDS = ("related_item", "product_family", "applicable_standard", "security_classification")


def _latest_revision_doc(drawing_number):
	rows = frappe.get_all(
		"Engineering Drawing",
		filters={"drawing_number": drawing_number},
		fields=["name"],
		order_by="creation desc",
		limit=1,
	)
	if not rows:
		return None
	return frappe.get_doc("Engineering Drawing", rows[0].name)


def create_new_drawing_revision(drawing_number, new_revision, **fields):
	source = _latest_revision_doc(drawing_number)
	if not source or source.release_status != "Released":
		frappe.throw(_("A new revision can only be created from a Released drawing."))

	new_fields = {
		"doctype": "Engineering Drawing",
		"drawing_number": drawing_number,
		"drawing_revision": new_revision,
	}
	for fieldname in CARRY_FORWARD_FIELDS:
		new_fields[fieldname] = source.get(fieldname)
	new_fields.update(fields)

	new_drawing = frappe.get_doc(new_fields).insert()
	log_audit_event(
		"Drawing Revision Creation",
		"Engineering Drawing",
		new_drawing.name,
		{"drawing_number": drawing_number, "new_revision": new_revision, "source_revision": source.name},
	)
	return new_drawing


def compare_drawing_revisions(drawing_number, revision_a, revision_b):
	name_a = f"{drawing_number}-{revision_a}"
	name_b = f"{drawing_number}-{revision_b}"
	doc_a = frappe.get_doc("Engineering Drawing", name_a).as_dict()
	doc_b = frappe.get_doc("Engineering Drawing", name_b).as_dict()

	diff = {}
	for fieldname in doc_b:
		if fieldname in BOOKKEEPING_FIELDS:
			continue
		if doc_a.get(fieldname) != doc_b.get(fieldname):
			diff[fieldname] = {"from": doc_a.get(fieldname), "to": doc_b.get(fieldname)}
	return diff


def retrieve_released_drawing_metadata(drawing_number):
	rows = frappe.get_all(
		"Engineering Drawing",
		filters={"drawing_number": drawing_number, "release_status": "Released"},
		fields=["name"],
		order_by="creation desc",
		limit=1,
	)
	if not rows:
		rows = frappe.get_all(
			"Engineering Drawing",
			filters={"drawing_number": drawing_number},
			fields=["name"],
			order_by="creation desc",
			limit=1,
		)
	if not rows:
		return None
	return frappe.get_doc("Engineering Drawing", rows[0].name).as_dict()
