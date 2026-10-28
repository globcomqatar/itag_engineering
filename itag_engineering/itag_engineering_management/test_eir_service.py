# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from itag_engineering.itag_engineering_management.classification_service import (
	product_type_options,
	resolve_product_type,
)
from itag_engineering.itag_engineering_management.eir_service import (
	approve_eir,
	create_item_from_eir,
	reject_eir,
	run_duplicate_check,
)
from itag_engineering.tests.factories import ensure_classification_value


def _insert_series(rule_name, prefix, series_name):
	return frappe.get_doc(
		{
			"doctype": "Item Code Rule",
			"rule_name": rule_name,
			"series_name": series_name,
			"code_prefix": prefix,
			"sequence_digits": 5,
			"is_active": 1,
			"priority": 0,
			"company": "",
			"separator": "-",
			"case_conversion": "As Entered",
		}
	).insert()


def _create_item_from_series(rule_name, title, item_type):
	eir = frappe.get_doc(
		{
			"doctype": "Engineering Item Request",
			"request_title": title,
			"item_category": "Manufactured",
			"item_type": item_type,
			"is_new_item_code": 1,
			"item_code_rule": rule_name,
			"duplicate_check_status": "No Duplicates Found",
		}
	).insert()
	frappe.db.set_value("Engineering Item Request", eir.name, "workflow_state", "Approved")
	return create_item_from_eir(eir.name)


class TestEirService(FrappeTestCase):
	def setUp(self):
		frappe.db.delete("Engineering Item Request", {"request_title": ["like", "EIRSVC Test%"]})
		frappe.db.delete("Item", {"item_code": ["like", "EIRSVC-%"]})
		frappe.db.delete("Item Code Rule", {"rule_name": "EIRSVC Test Rule"})
		frappe.db.delete("Item Code Reservation", {"rule": "EIRSVC Test Rule"})

		self.rule = frappe.get_doc(
			{
				"doctype": "Item Code Rule",
				"rule_name": "EIRSVC Test Rule",
				"is_active": 1,
				"priority": 100,
				"separator": "-",
				"case_conversion": "Upper",
				"segments": [
					{"segment_type": "Fixed Prefix", "fixed_value": "EIRSVC"},
					{"segment_type": "Sequence", "sequence_digits": 3},
				],
			}
		).insert()

		ensure_classification_value("Nominal Size", "6IN")
		ensure_classification_value("Pressure Class", "CL300")
		self.eir = frappe.get_doc(
			{
				"doctype": "Engineering Item Request",
				"request_title": "EIRSVC Test New Valve",
				"item_category": "Manufactured",
				"product_family": "CS",
				"valve_type": "BALL",
				"nominal_size": "6IN",
				"pressure_class": "CL300",
				"item_description": "Cast steel gate valve, 6 inch, class 300, per EIRSVC test spec.",
				"is_new_item_code": 1,
				"item_code_rule": self.rule.name,
			}
		).insert()

	def tearDown(self):
		frappe.db.delete("Item", {"item_code": ["like", "EIRSVC-%"]})
		frappe.db.delete("Item Code Reservation", {"rule": "EIRSVC Test Rule"})
		frappe.db.delete("Engineering Item Request", {"request_title": ["like", "EIRSVC Test%"]})
		frappe.db.delete("Item Code Rule", {"rule_name": "EIRSVC Test Rule"})

	def test_duplicate_check_updates_eir_status(self):
		results = run_duplicate_check(self.eir.name)
		self.eir.reload()
		self.assertEqual(results, [])
		self.assertEqual(self.eir.duplicate_check_status, "No Duplicates Found")

	def test_non_privileged_user_cannot_run_duplicate_check(self):
		frappe.set_user("Guest")
		try:
			with self.assertRaises(frappe.PermissionError):
				run_duplicate_check(self.eir.name)
		finally:
			frappe.set_user("Administrator")

	def test_privileged_user_can_run_duplicate_check(self):
		# Administrator (the default test user) holds every role, including the
		# Engineering roles in CREATE_ITEM_ROLES, so this must still succeed.
		results = run_duplicate_check(self.eir.name)
		self.eir.reload()
		self.assertEqual(results, [])
		self.assertEqual(self.eir.duplicate_check_status, "No Duplicates Found")

	def test_create_item_requires_approved_state(self):
		with self.assertRaises(frappe.ValidationError):
			create_item_from_eir(self.eir.name)

	def test_create_item_from_approved_eir_creates_exactly_one_item(self):
		frappe.db.set_value("Engineering Item Request", self.eir.name, "workflow_state", "Approved")
		item_code = create_item_from_eir(self.eir.name)
		self.assertTrue(frappe.db.exists("Item", item_code))
		self.eir.reload()
		self.assertEqual(self.eir.created_item, item_code)
		self.assertEqual(self.eir.workflow_state, "Item Created")
		self.assertEqual(
			frappe.db.get_value("Item Code Reservation", {"item_code": item_code}, "status"), "Consumed"
		)

	def test_valve_type_chooses_the_item_code_series(self):
		series = _insert_series("EIRSVC980", "980", "Sample Plate")
		_insert_series("EIRSVC981", "981", "Other Plate")
		frappe.get_doc(
			{
				"doctype": "Valve Type",
				"valve_type_code": "EIRSVC980",
				"valve_type_name": "Sample Plate",
				"item_code_rule": series.name,
			}
		).insert()
		eir = frappe.get_doc(
			{
				"doctype": "Engineering Item Request",
				"request_title": "EIRSVC Test From Valve Type",
				"item_category": "Manufactured",
				"valve_type": "EIRSVC980",
				"item_code_rule": "EIRSVC981",
				"is_new_item_code": 1,
				"duplicate_check_status": "No Duplicates Found",
			}
		).insert()
		self.assertEqual(eir.item_code_rule, "EIRSVC980")
		self.assertEqual(eir.code_pattern, "980-#####")

		frappe.db.set_value(
			"Engineering Item Request",
			eir.name,
			{"workflow_state": "Approved", "item_code_rule": "EIRSVC981"},
		)
		self.assertEqual(create_item_from_eir(eir.name), "980-00001")
		eir.reload()
		self.assertEqual(eir.item_code_rule, "EIRSVC980")
		self.assertEqual(frappe.db.get_value("Item", "980-00001", "itag_valve_type"), "EIRSVC980")

	def test_series_rules_number_items_independently(self):
		for name in ("EIRSVC990", "EIRSVC992"):
			frappe.db.delete("Item Code Reservation", {"rule": name})
			frappe.db.delete("Item Code Rule Segment", {"parent": name})
			frappe.db.delete("Item Code Rule", {"name": name})
		tag = _insert_series("EIRSVC990", "990", "Tag Plate")
		indicator = _insert_series("EIRSVC992", "992", "Indicator Plate")
		first = _create_item_from_series(tag.name, "EIRSVC Test Tag Plate 50mm", "Critical")
		second = _create_item_from_series(tag.name, "EIRSVC Test Tag Plate 80mm", "General")
		other = _create_item_from_series(indicator.name, "EIRSVC Test Indicator Plate", "Non-Critical")

		self.assertEqual(first, "990-00001")
		self.assertEqual(second, "990-00002")
		self.assertEqual(other, "992-00001")
		if frappe.get_meta("Item").has_field("custom_product_type"):
			self.assertEqual(frappe.db.get_value("Item", first, "custom_product_type"), "Critical")
			self.assertEqual(frappe.db.get_value("Item", other, "custom_product_type"), "Non-Critical")

	def test_create_item_copies_item_description_to_item(self):
		frappe.db.set_value("Engineering Item Request", self.eir.name, "workflow_state", "Approved")
		item_code = create_item_from_eir(self.eir.name)
		self.assertEqual(
			frappe.db.get_value("Item", item_code, "description"),
			"Cast steel gate valve, 6 inch, class 300, per EIRSVC test spec.",
		)

	def test_create_item_is_idempotent_on_retry(self):
		frappe.db.set_value("Engineering Item Request", self.eir.name, "workflow_state", "Approved")
		first_code = create_item_from_eir(self.eir.name)
		second_code = create_item_from_eir(self.eir.name)
		self.assertEqual(first_code, second_code)
		self.assertEqual(frappe.db.count("Item", {"item_code": first_code}), 1)

	def test_approve_eir_makes_the_request_approved_and_item_creatable(self):
		self.assertEqual(self.eir.workflow_state, "Draft")
		approve_eir(self.eir.name)
		self.eir.reload()
		self.assertEqual(self.eir.workflow_state, "Approved")
		# The duplicate check ran as part of the approval.
		self.assertEqual(self.eir.duplicate_check_status, "No Duplicates Found")
		self.assertTrue(
			frappe.db.exists(
				"Comment",
				{
					"reference_doctype": "Engineering Item Request",
					"reference_name": self.eir.name,
					"comment_type": "Comment",
					"content": ["like", "%Approved by%"],
				},
			)
		)
		# Needs the "EIR Transition" option on Engineering Audit Log.event_type,
		# which arrives with the doctype sync (bench migrate).
		self.assertTrue(
			frappe.db.exists(
				"Engineering Audit Log", {"event_type": "EIR Transition", "reference_name": self.eir.name}
			)
		)
		item_code = create_item_from_eir(self.eir.name)
		self.assertTrue(frappe.db.exists("Item", item_code))
		self.eir.reload()
		self.assertEqual(self.eir.workflow_state, "Item Created")

	def test_approve_eir_is_blocked_while_possible_duplicates_are_unresolved(self):
		frappe.db.set_value(
			"Engineering Item Request",
			self.eir.name,
			"duplicate_check_status",
			"Possible Duplicates Found",
		)
		with self.assertRaises(frappe.ValidationError):
			approve_eir(self.eir.name)
		self.assertEqual(frappe.db.get_value("Engineering Item Request", self.eir.name, "workflow_state"), "Draft")

	def test_approve_eir_requires_engineering_manager(self):
		frappe.set_user("Guest")
		try:
			with self.assertRaises(frappe.PermissionError):
				approve_eir(self.eir.name)
			with self.assertRaises(frappe.PermissionError):
				reject_eir(self.eir.name, "Not needed")
		finally:
			frappe.set_user("Administrator")
		self.assertEqual(frappe.db.get_value("Engineering Item Request", self.eir.name, "workflow_state"), "Draft")

	def test_approve_eir_only_from_open_states(self):
		for state in ("Approved", "Item Created", "Rejected", "Closed", "Cancelled"):
			frappe.db.set_value("Engineering Item Request", self.eir.name, "workflow_state", state)
			with self.assertRaises(frappe.ValidationError, msg=f"approve from {state}"):
				approve_eir(self.eir.name)

	def test_reject_eir_needs_a_reason_and_is_final(self):
		with self.assertRaises(frappe.ValidationError):
			reject_eir(self.eir.name, "  ")
		reject_eir(self.eir.name, "Duplicate of an existing catalogue item")
		self.eir.reload()
		self.assertEqual(self.eir.workflow_state, "Rejected")
		self.assertTrue(
			frappe.db.exists(
				"Comment",
				{
					"reference_doctype": "Engineering Item Request",
					"reference_name": self.eir.name,
					"content": ["like", "%Rejected by%Duplicate of an existing catalogue item%"],
				},
			)
		)
		with self.assertRaises(frappe.ValidationError):
			approve_eir(self.eir.name)
		with self.assertRaises(frappe.ValidationError):
			create_item_from_eir(self.eir.name)

	def test_item_type_of_the_request_becomes_the_items_product_type(self):
		if not product_type_options():
			self.skipTest("Item has no custom_product_type field on this site.")
		frappe.db.set_value("Engineering Item Request", self.eir.name, "item_type", "Critical")
		approve_eir(self.eir.name)
		item_code = create_item_from_eir(self.eir.name)
		self.assertEqual(frappe.db.get_value("Item", item_code, "custom_product_type"), "Critical")

	def test_resolve_product_type_defaults_and_rejects_unknown_values(self):
		options = product_type_options()
		if not options:
			self.assertIsNone(resolve_product_type("Critical"))
			return
		self.assertEqual(resolve_product_type(None), "General")
		self.assertEqual(resolve_product_type("Non-Critical"), "Non-Critical")
		with self.assertRaises(frappe.ValidationError):
			resolve_product_type("Not A Product Type")
