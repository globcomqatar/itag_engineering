# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class ChangeImpactAssessment(Document):
	"""Frappe's "JSON" fieldtype only auto-serializes dict -> str on
	Document.save() (base_document.py's get_valid_dict()) - confirmed live
	against this bench that there is NO symmetric str -> dict step on load:
	Document.load_from_db() fetches every column via frappe.db.get_value(...,
	fieldname="*") and assigns it straight into self.__dict__ with no
	per-fieldtype post-processing, so a freshly frappe.get_doc()'d/.reload()'d
	assessment's impact_results/summary_counts are raw JSON strings, not
	dicts - the exact "TypeError: string indices must be integers, not
	'str'" crash every domain-scan test hit.

	These two properties parse the raw string back into a dict on read,
	without disturbing anything else: BaseDocument.set()/update() (used by
	load_from_db()) write straight into self.__dict__, bypassing
	__setattr__/property setters entirely, so this pair only intercepts
	genuine dotted attribute access (doc.impact_results) - the bulk
	field-loading path is untouched. get_valid_dict() (the save/as_dict
	path) also reads straight from self.__dict__, so it keeps serializing
	whatever raw value is actually stored (a dict pre-save, a str
	post-load) exactly as before this fix.
	"""

	@property
	def impact_results(self):
		raw = self.__dict__.get("impact_results")
		return frappe.parse_json(raw) if isinstance(raw, str) else (raw or {})

	@impact_results.setter
	def impact_results(self, value):
		self.__dict__["impact_results"] = value

	@property
	def summary_counts(self):
		raw = self.__dict__.get("summary_counts")
		return frappe.parse_json(raw) if isinstance(raw, str) else (raw or {})

	@summary_counts.setter
	def summary_counts(self, value):
		self.__dict__["summary_counts"] = value
