# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

FIELDS = (
	"reference_doctype",
	"existing_record",
	"existing_revision",
	"proposed_record",
	"proposed_revision",
	"change_description",
	"interchangeability",
	"required_new_item_code",
	"required_rework",
	"required_inspection",
	"required_documentation",
	"implementation_status",
)


class TestControlledChange(FrappeTestCase):
	def test_fields_exist(self):
		meta = frappe.get_meta("Controlled Change")
		for fieldname in FIELDS:
			self.assertTrue(meta.has_field(fieldname), f"Controlled Change missing {fieldname}")

	def test_is_a_child_table(self):
		self.assertTrue(frappe.get_meta("Controlled Change").istable)

	def test_existing_record_is_dynamic_link_on_reference_doctype(self):
		meta = frappe.get_meta("Controlled Change")
		df = meta.get_field("existing_record")
		self.assertEqual(df.fieldtype, "Dynamic Link")
		self.assertEqual(df.options, "reference_doctype")

	def test_proposed_record_is_data_not_a_link(self):
		# Deliberate: the proposed new record commonly does not exist yet at
		# ECO-drafting time, matching this app's established
		# forward-reference-as-Data pattern (see Global Constraints).
		df = frappe.get_meta("Controlled Change").get_field("proposed_record")
		self.assertEqual(df.fieldtype, "Data")


# NOTE: this build's own plan (Task 3, Step 1) asks for a live test that
# inserts a real Controlled Change row referencing an actual Item and
# confirms frappe.get_doc(row.reference_doctype, row.existing_record)
# resolves. Controlled Change is a child table with no standalone list
# view - inserting one requires a real parent doctype with a Table field
# pointing at it, and no such parent exists yet in this task (Engineering
# Change Order, which owns the `controlled_changes` Table field, is Build
# ITAG-0.6.0 Task 4). That live Dynamic Link resolution test is therefore
# covered in test_eco_service.py instead, against a real Engineering Change
# Order's controlled_changes rows - not skipped, just sequenced where a
# real parent actually exists.
