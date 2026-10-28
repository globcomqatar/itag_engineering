# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import now_datetime

from itag_engineering.tests.factories import (
	create_fresh_stock_item,
	create_test_bom_with_operations,
	ensure_test_company,
)


class TestEngineeringRelease(FrappeTestCase):
	def setUp(self):
		frappe.db.delete("Engineering Release", {"item": ["like", "ER-TEST-ITEM%"]})

	def tearDown(self):
		frappe.db.delete("Engineering Release", {"item": ["like", "ER-TEST-ITEM%"]})
		frappe.set_user("Administrator")

	def _make_baseline(self):
		item = create_fresh_stock_item("ER-TEST-ITEM").name
		return create_test_bom_with_operations(item=item)

	def _make_release(self, bom=None):
		bom = bom or self._make_baseline()
		return frappe.get_doc(
			{
				"doctype": "Engineering Release",
				"company": ensure_test_company(),
				"item": bom.item,
				"product_revision": bom.itag_product_revision,
				"drawing_revision": bom.itag_drawing_revision,
				"bom": bom.name,
				"effective_datetime": now_datetime(),
			}
		).insert()

	def test_create_with_full_baseline(self):
		release = self._make_release()
		self.assertTrue(release.name.startswith("ER-"))
		self.assertEqual(release.release_status, "Draft")

	def test_workflow_transition_happy_path(self):
		release = self._make_release()
		for state in (
			"Engineering Review",
			"Engineering Checked",
			"Quality Review",
			"Manufacturing Review",
			"Engineering Approved",
		):
			release.db_set("release_status", state)
			release.reload()
			self.assertEqual(release.release_status, state)

	def test_immutable_once_released_for_production(self):
		release = self._make_release()
		release.db_set({"release_status": "Released for Production", "release_checksum": "test-checksum"})
		release.reload()
		release.applicable_standards = "Changed after release"
		with self.assertRaises(frappe.ValidationError):
			release.save()

	def test_immutable_once_released_for_production_child_tables(self):
		release = self._make_release()
		release.db_set({"release_status": "Released for Production", "release_checksum": "test-checksum"})
		release.reload()
		release.append("release_checklist", {"checklist_item": "Added after release"})
		with self.assertRaises(frappe.ValidationError):
			release.save()

	def test_raw_workflow_transition_to_released_for_production_without_checksum_is_blocked(self):
		release = self._make_release()
		release.db_set("release_status", "Engineering Approved")
		release.reload()
		release.release_status = "Released for Production"
		with self.assertRaises(frappe.ValidationError):
			release.save()

	def _make_released(self, release=None):
		"""Put a release at Released for Production. db_set skips validate(), the
		way the existing tests here reach that state. Pass an existing release to
		reset it between loop iterations instead of building another baseline."""
		release = release or self._make_release()
		release.db_set({"release_status": "Released for Production", "release_checksum": "test-checksum"})
		release.reload()
		return release

	def test_released_for_production_cannot_be_saved_back_to_another_status(self):
		"""Guard against a plain save moving a released package back to Draft (or
		to a review step, or forward to an approval state)."""
		release = None
		for target in (
			"Draft",
			"Engineering Review",
			"Engineering Checked",
			"Quality Review",
			"Manufacturing Review",
			"Engineering Approved",
		):
			release = self._make_released(release)
			release.release_status = target
			with self.assertRaises(frappe.ValidationError, msg=target):
				release.save()
			release.reload()
			self.assertEqual(release.release_status, "Released for Production", target)

	def test_released_for_production_can_still_leave_through_the_post_release_states(self):
		release = None
		for target in ("Suspended", "Withdrawn", "Superseded", "Obsolete"):
			release = self._make_released(release)
			release.release_status = target
			release.save()
			release.reload()
			self.assertEqual(release.release_status, target)

	def test_suspended_superseded_and_obsolete_releases_are_final(self):
		release = None
		for final_state in ("Suspended", "Withdrawn", "Superseded", "Obsolete"):
			release = self._make_released(release)
			release.release_status = final_state
			release.save()
			release.release_status = "Released for Production"
			with self.assertRaises(frappe.ValidationError, msg=final_state):
				release.save()
			release.reload()
			self.assertEqual(release.release_status, final_state)

	def test_unchanged_status_on_a_released_release_still_hits_the_immutability_guard(self):
		release = self._make_released()
		release.applicable_standards = "Changed after release"
		with self.assertRaises(frappe.ValidationError) as ctx:
			release.save()
		self.assertIn("cannot be changed once", str(ctx.exception))

	def test_non_admin_cannot_create_release(self):
		bom = self._make_baseline()
		frappe.set_user("Guest")
		try:
			with self.assertRaises(frappe.PermissionError):
				frappe.get_doc(
					{
						"doctype": "Engineering Release",
						"company": ensure_test_company(),
						"item": bom.item,
						"product_revision": bom.itag_product_revision,
						"drawing_revision": bom.itag_drawing_revision,
						"bom": bom.name,
						"effective_datetime": now_datetime(),
					}
				).insert()
		finally:
			frappe.set_user("Administrator")
