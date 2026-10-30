"""v15.5.14 #6 (Waheed, 30-Oct-2026): item codes via Frappe's standard
Document Naming Rule.

Ordering, verified in frappe/model/naming.py set_new_name() and
frappe/model/document.py insert():
  before_insert -> set_new_name():
      amended -> Document Naming Rule (set_naming_from_document_naming_rule)
      -> doc.autoname() (ERPNext Item.autoname: Stock Settings
         "Item Naming By" / naming series, then name = item_code)
      -> meta autoname -> hash
  -> before_validate -> validate.
A matching Document Naming Rule therefore names the Item BEFORE ERPNext's
Item.autoname runs, so Stock Settings' naming series never applies, but
item_code is left as whatever was passed in (blank). This hook is the glue:
on insert, item_code = name. ERPNext/Frappe core is not changed.
"""

import frappe
from frappe.utils.data import evaluate_filters


def matching_document_naming_rule(doc):
	"""Name of the highest-priority enabled Document Naming Rule for
	doc.doctype whose conditions match `doc` (same evaluation as Frappe's
	DocumentNamingRule.apply), else None."""
	rules = frappe.get_all(
		"Document Naming Rule",
		filters={"document_type": doc.doctype, "disabled": 0},
		fields=["name"],
		order_by="priority desc",
	)
	for row in rules:
		rule = frappe.get_cached_doc("Document Naming Rule", row.name)
		if rule.conditions and not evaluate_filters(
			doc, [(rule.document_type, c.field, c.condition, c.value) for c in rule.conditions]
		):
			continue
		return rule.name
	return None


def sync_item_code_with_naming_rule(doc, method=None):
	"""Item.before_validate. Only on insert: when the name was set by a
	Document Naming Rule (so it differs from item_code), copy it into
	item_code. Saved Items are never renamed or re-coded here."""
	if not doc.flags.in_insert or not doc.name:
		return
	if doc.item_code != doc.name:
		doc.item_code = doc.name
