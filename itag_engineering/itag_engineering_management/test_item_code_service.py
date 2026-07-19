# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from itag_engineering.itag_engineering_management.item_code_service import (
	preview_item_code,
	render_segments,
	resolve_rule,
)


class TestItemCodeService(FrappeTestCase):
	def setUp(self):
		frappe.db.delete("Item Code Rule", {"rule_name": ["like", "ICS Test%"]})
		self.rule = frappe.get_doc(
			{
				"doctype": "Item Code Rule",
				"rule_name": "ICS Test Rule High Priority",
				"is_active": 1,
				"priority": 10,
				# Explicitly blank: Frappe auto-fills any Link field named "company" from the
				# site's default company (Global Defaults) on insert() when left unset. This
				# site has one configured, so without this the rule would come back scoped to
				# that company and resolve_rule(company=None) would never match it.
				"company": "",
				"separator": "-",
				"case_conversion": "Upper",
				"segments": [
					{"segment_type": "Product Family", "source_fieldname": "itag_product_family"},
					{"segment_type": "Valve Type", "source_fieldname": "itag_valve_type"},
					{"segment_type": "Sequence", "sequence_digits": 3},
				],
			}
		).insert()
		self.low_priority_rule = frappe.get_doc(
			{
				"doctype": "Item Code Rule",
				"rule_name": "ICS Test Rule Low Priority",
				"is_active": 1,
				"priority": 1,
				"company": "",
				"separator": "-",
				"case_conversion": "Upper",
				"segments": [{"segment_type": "Sequence", "sequence_digits": 3}],
			}
		).insert()

	def tearDown(self):
		frappe.db.delete("Item Code Rule", {"rule_name": ["like", "ICS Test%"]})

	def test_resolve_rule_picks_highest_priority_active_rule(self):
		rule = resolve_rule()
		self.assertEqual(rule.rule_name, "ICS Test Rule High Priority")

	def test_resolve_rule_ignores_inactive_rules(self):
		self.rule.is_active = 0
		self.rule.save()
		rule = resolve_rule()
		self.assertEqual(rule.rule_name, "ICS Test Rule Low Priority")

	def test_render_segments_renders_field_values(self):
		segments = render_segments(self.rule, {"itag_product_family": "gate", "itag_valve_type": "ball"})
		self.assertEqual(segments[0], "gate")
		self.assertEqual(segments[1], "ball")
		self.assertEqual(segments[2], "000")

	def test_preview_item_code_joins_and_cases(self):
		code = preview_item_code(self.rule, {"itag_product_family": "gate", "itag_valve_type": "ball"})
		self.assertEqual(code, "GATE-BALL-000")

	def test_preview_item_code_missing_source_field_renders_blank(self):
		code = preview_item_code(self.rule, {})
		self.assertEqual(code, "-000")
