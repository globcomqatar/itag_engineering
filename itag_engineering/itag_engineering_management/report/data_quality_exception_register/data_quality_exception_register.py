"""Data Quality Exception Register (roadmap Section 22.10).

A consolidated rollup over several EXISTING exception conditions already
tracked by their own dedicated field/report elsewhere in this app (Items
Missing Engineering Classification, BOM Release-Readiness Exceptions,
Missing Engineering Baseline) plus one new check (Released Engineering
Drawings missing a file checksum - should be structurally impossible per
engineering_drawing.validate_release_requires_checksum(), so a genuine hit
here means a legacy record or a validate()-bypassing write path) - each
tagged with `exception_type` so this single register can be scanned across
domains rather than requiring one open tab per existing dedicated report.
"""

import frappe


def execute(filters=None):
	columns = [
		{"label": "Exception Type", "fieldname": "exception_type", "fieldtype": "Data", "width": 220},
		{"label": "DocType", "fieldname": "doctype", "fieldtype": "Data", "width": 150},
		{"label": "Document", "fieldname": "name", "fieldtype": "Data", "width": 200},
		{"label": "Detail", "fieldname": "detail", "fieldtype": "Data", "width": 300},
	]
	data = (
		_items_missing_engineering_classification()
		+ _bom_release_readiness_exceptions()
		+ _missing_engineering_baseline_work_orders()
		+ _released_drawings_missing_checksum()
	)
	return columns, data


def _items_missing_engineering_classification():
	rows = frappe.get_all(
		"Item",
		filters={"itag_engineering_classification": ["in", ["", None]]},
		fields=["item_code"],
	)
	return [
		{
			"exception_type": "Item Missing Engineering Classification",
			"doctype": "Item",
			"name": row.item_code,
			"detail": "Engineering Classification is blank.",
		}
		for row in rows
	]


def _bom_release_readiness_exceptions():
	rows = frappe.get_all("BOM", filters={"itag_release_readiness_status": "Exception"}, fields=["name"])
	return [
		{
			"exception_type": "BOM Release-Readiness Exception",
			"doctype": "BOM",
			"name": row.name,
			"detail": "One or more roadmap Section 12.4 readiness criteria are unmet.",
		}
		for row in rows
	]


def _missing_engineering_baseline_work_orders():
	rows = frappe.get_all(
		"Work Order",
		filters={"docstatus": 1, "itag_engineering_release": ["in", ["", None]]},
		fields=["name"],
	)
	return [
		{
			"exception_type": "Work Order Missing Engineering Baseline",
			"doctype": "Work Order",
			"name": row.name,
			"detail": "Submitted with no frozen Engineering Release baseline.",
		}
		for row in rows
	]


def _released_drawings_missing_checksum():
	rows = frappe.get_all(
		"Engineering Drawing",
		filters={"release_status": "Released", "file_checksum": ["in", ["", None]]},
		fields=["name"],
	)
	return [
		{
			"exception_type": "Released Drawing Missing Checksum",
			"doctype": "Engineering Drawing",
			"name": row.name,
			"detail": "Released with no recorded file checksum.",
		}
		for row in rows
	]
