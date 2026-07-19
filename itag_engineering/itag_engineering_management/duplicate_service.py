"""Possible-duplicate Item detection (roadmap Section 10.6)."""

import frappe

from itag_engineering.itag_engineering_management.response import success

MATCHABLE_FIELDS = (
	"itag_product_family",
	"itag_valve_type",
	"itag_nominal_size",
	"itag_pressure_class",
	"itag_body_material",
	"itag_trim_material",
	"itag_end_connection",
	"itag_drawing_number",
)


def find_possible_duplicates(
	product_family=None,
	valve_type=None,
	nominal_size=None,
	pressure_class=None,
	body_material=None,
	trim_material=None,
	end_connection=None,
	drawing_number=None,
	item_name=None,
):
	criteria = {
		"itag_product_family": product_family,
		"itag_valve_type": valve_type,
		"itag_nominal_size": nominal_size,
		"itag_pressure_class": pressure_class,
		"itag_body_material": body_material,
		"itag_trim_material": trim_material,
		"itag_end_connection": end_connection,
		"itag_drawing_number": drawing_number,
	}
	criteria = {k: v for k, v in criteria.items() if v}
	if not criteria:
		return []

	or_filters = [[fieldname, "=", value] for fieldname, value in criteria.items()]
	candidates = frappe.get_all(
		"Item",
		or_filters=or_filters,
		fields=["item_code", "item_name", *MATCHABLE_FIELDS],
	)

	results = []
	for candidate in candidates:
		matched_fields = [
			fieldname
			for fieldname, value in criteria.items()
			if candidate.get(fieldname) and candidate.get(fieldname) == value
		]
		if matched_fields:
			results.append(
				{
					"item_code": candidate.item_code,
					"item_name": candidate.item_name,
					"match_score": len(matched_fields),
					"matched_fields": matched_fields,
				}
			)

	results.sort(key=lambda r: r["match_score"], reverse=True)
	return results


@frappe.whitelist()
def search_similar_items_api(**kwargs):
	results = find_possible_duplicates(**kwargs)
	return success(data={"results": results})
