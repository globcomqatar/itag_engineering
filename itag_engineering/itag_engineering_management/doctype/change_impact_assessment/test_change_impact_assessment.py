# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import now_datetime

from itag_engineering.tests.factories import create_eco_from_accepted_ecr_factory

FIELDS = (
	"eco",
	"analysis_version",
	"analysis_status",
	"started_at",
	"completed_at",
	"input_checksum",
	"scope",
	"company",
	"facility",
	"effective_cutoff",
	"progress",
	"error_status",
	"staleness_status",
	"impact_results",
	"summary_counts",
	"analyst_review",
	"final_approval",
	"approved_by",
	"approved_on",
)


class TestChangeImpactAssessment(FrappeTestCase):
	def setUp(self):
		frappe.db.delete("Engineering Change Request", {"request_title": ["like", "CIA-DOCTEST%"]})

	def tearDown(self):
		frappe.db.delete("Engineering Change Request", {"request_title": ["like", "CIA-DOCTEST%"]})

	def _make_assessment(self, **overrides):
		eco = create_eco_from_accepted_ecr_factory(request_title="CIA-DOCTEST ECR")
		fields = {
			"doctype": "Change Impact Assessment",
			"eco": eco.name,
			"effective_cutoff": now_datetime(),
		}
		fields.update(overrides)
		return frappe.get_doc(fields).insert(ignore_permissions=True)

	def test_all_fields_exist(self):
		meta = frappe.get_meta("Change Impact Assessment")
		for fieldname in FIELDS:
			self.assertTrue(meta.has_field(fieldname), f"Change Impact Assessment missing {fieldname}")

	def test_defaults(self):
		assessment = self._make_assessment()
		self.assertEqual(assessment.analysis_status, "Queued")
		self.assertEqual(assessment.staleness_status, "Fresh")
		self.assertEqual(assessment.analysis_version, 1)

	def test_json_field_round_trips_as_a_real_dict(self):
		# Task 2's own live-verification finding: JSON fieldtype is new to
		# this app. Confirms a dict value survives insert + reload as a
		# real Python dict, not a JSON-encoded string, before any service
		# code relies on that. If this fails against a real bench, fall
		# back to fieldtype "Code" (options "JSON") with manual
		# json.loads/json.dumps in impact_analysis_service.py instead.
		assessment = self._make_assessment()
		assessment.impact_results = {"bom_where_used": {"count": 2, "items": ["A", "B"]}}
		assessment.summary_counts = {"bom_where_used": 2}
		assessment.save(ignore_permissions=True)
		assessment.reload()

		self.assertIsInstance(assessment.impact_results, dict)
		self.assertEqual(assessment.impact_results["bom_where_used"]["count"], 2)
		self.assertIsInstance(assessment.summary_counts, dict)
		self.assertEqual(assessment.summary_counts["bom_where_used"], 2)
