import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def get_custom_fields():
	return {
		"Item": [
			{
				"fieldname": "itag_engineering_tab",
				"label": "Engineering",
				"fieldtype": "Tab Break",
				"insert_after": "inspection_required_before_delivery",
			},
			{
				"fieldname": "itag_engineering_classification",
				"label": "Engineering Classification",
				"fieldtype": "Select",
				"options": "\nManufactured\nPurchased\nRaw Material\nSub-Assembly",
				"insert_after": "itag_engineering_tab",
			},
			{
				"fieldname": "itag_product_family",
				"label": "Product Family",
				"fieldtype": "Data",
				"insert_after": "itag_engineering_classification",
			},
			{
				"fieldname": "itag_valve_type",
				"label": "Valve Type",
				"fieldtype": "Data",
				"insert_after": "itag_product_family",
			},
			{
				"fieldname": "itag_column_break_1",
				"fieldtype": "Column Break",
				"insert_after": "itag_valve_type",
			},
			{
				"fieldname": "itag_nominal_size",
				"label": "Nominal Size",
				"fieldtype": "Data",
				"insert_after": "itag_column_break_1",
			},
			{
				"fieldname": "itag_pressure_class",
				"label": "Pressure Class",
				"fieldtype": "Data",
				"insert_after": "itag_nominal_size",
			},
			{
				"fieldname": "itag_body_material",
				"label": "Body Material",
				"fieldtype": "Data",
				"insert_after": "itag_pressure_class",
			},
			{
				"fieldname": "itag_trim_material",
				"label": "Trim Material",
				"fieldtype": "Data",
				"insert_after": "itag_body_material",
			},
			{
				"fieldname": "itag_end_connection",
				"label": "End Connection",
				"fieldtype": "Data",
				"insert_after": "itag_trim_material",
			},
			{
				"fieldname": "itag_engineering_section_2",
				"fieldtype": "Section Break",
				"label": "Design & Drawing",
				"insert_after": "itag_end_connection",
			},
			{
				"fieldname": "itag_design_standard",
				"label": "Design Standard",
				"fieldtype": "Data",
				"insert_after": "itag_engineering_section_2",
			},
			{
				"fieldname": "itag_manufacturing_method",
				"label": "Manufacturing Method",
				"fieldtype": "Data",
				"insert_after": "itag_design_standard",
			},
			{
				"fieldname": "itag_drawing_number",
				"label": "Drawing Number",
				"fieldtype": "Data",
				"insert_after": "itag_manufacturing_method",
			},
			{
				"fieldname": "itag_column_break_2",
				"fieldtype": "Column Break",
				"insert_after": "itag_drawing_number",
			},
			{
				"fieldname": "itag_current_drawing_revision",
				"label": "Current Drawing Revision",
				"fieldtype": "Data",
				"read_only": 1,
				"insert_after": "itag_column_break_2",
			},
			{
				"fieldname": "itag_current_product_revision",
				"label": "Current Product Revision",
				"fieldtype": "Data",
				"read_only": 1,
				"insert_after": "itag_current_drawing_revision",
			},
			{
				"fieldname": "itag_engineering_section_3",
				"fieldtype": "Section Break",
				"label": "Engineering Status",
				"insert_after": "itag_current_product_revision",
			},
			{
				"fieldname": "itag_engineering_status",
				"label": "Engineering Status",
				"fieldtype": "Select",
				"options": "\nDraft\nApproved\nReleased\nObsolete",
				"read_only": 1,
				"insert_after": "itag_engineering_section_3",
			},
			{
				"fieldname": "itag_engineering_release",
				"label": "Engineering Release",
				"fieldtype": "Data",
				"read_only": 1,
				"insert_after": "itag_engineering_status",
			},
			{
				"fieldname": "itag_column_break_3",
				"fieldtype": "Column Break",
				"insert_after": "itag_engineering_release",
			},
			{
				"fieldname": "itag_effective_date",
				"label": "Effective Date",
				"fieldtype": "Date",
				"insert_after": "itag_column_break_3",
			},
			{
				"fieldname": "itag_obsolete_date",
				"label": "Obsolete Date",
				"fieldtype": "Date",
				"insert_after": "itag_effective_date",
			},
			{
				"fieldname": "itag_engineering_section_4",
				"fieldtype": "Section Break",
				"label": "Traceability Policy",
				"insert_after": "itag_obsolete_date",
				"description": "Per Decision Log #6.",
			},
			{
				"fieldname": "itag_serial_tracking_required",
				"label": "Serial Tracking Required",
				"fieldtype": "Check",
				"insert_after": "itag_engineering_section_4",
			},
			{
				"fieldname": "itag_batch_tracking_required",
				"label": "Batch Tracking Required",
				"fieldtype": "Check",
				"insert_after": "itag_serial_tracking_required",
			},
			{
				"fieldname": "itag_column_break_4",
				"fieldtype": "Column Break",
				"insert_after": "itag_batch_tracking_required",
			},
			{
				"fieldname": "itag_heat_tracking_required",
				"label": "Heat Tracking Required",
				"fieldtype": "Check",
				"insert_after": "itag_column_break_4",
			},
			{
				"fieldname": "itag_wip_unit_tracking_required",
				"label": "WIP Unit Tracking Required",
				"fieldtype": "Check",
				"insert_after": "itag_heat_tracking_required",
			},
		]
	}


def get_bom_fields():
	return {
		"BOM": [
			{
				"fieldname": "itag_engineering_tab",
				"fieldtype": "Tab Break",
				"label": "Engineering",
				# NOTE: brief specified "more_information" as the anchor, but that field
				# does not exist on BOM in this ERPNext version. Verified via the BOM
				# doctype JSON and tabDocField table that "column_break_oxbz" is the
				# last real field on the doctype, so it is used as the anchor instead.
				"insert_after": "column_break_oxbz",
			},
			{
				"fieldname": "itag_engineering_status",
				"fieldtype": "Select",
				"label": "Engineering Status",
				"options": "\nDraft\nUnder Review\nApproved\nReleased\nObsolete",
				"insert_after": "itag_engineering_tab",
			},
			{
				"fieldname": "itag_engineering_revision",
				"fieldtype": "Data",
				"label": "Engineering Revision",
				"insert_after": "itag_engineering_status",
			},
			{
				"fieldname": "itag_column_break_bom_1",
				"fieldtype": "Column Break",
				"insert_after": "itag_engineering_revision",
			},
			{
				"fieldname": "itag_product_revision",
				"fieldtype": "Link",
				"label": "Product Revision",
				"options": "Product Revision",
				"insert_after": "itag_column_break_bom_1",
			},
			{
				"fieldname": "itag_drawing_revision",
				"fieldtype": "Link",
				"label": "Drawing Revision",
				"options": "Engineering Drawing",
				"insert_after": "itag_product_revision",
			},
			{
				"fieldname": "itag_release_section",
				"fieldtype": "Section Break",
				"label": "Release Control",
				"insert_after": "itag_drawing_revision",
			},
			{
				"fieldname": "itag_engineering_release",
				"fieldtype": "Data",
				"label": "Engineering Release",
				"description": "Free-text identifier for now - Engineering Release (Build ITAG-0.5.0) does not exist yet.",
				"insert_after": "itag_release_section",
			},
			{
				"fieldname": "itag_applicable_eco",
				"fieldtype": "Data",
				"label": "Applicable ECO",
				"description": "Free-text identifier for now - ECR/ECO (Build ITAG-0.6.0) does not exist yet.",
				"insert_after": "itag_engineering_release",
			},
			{
				"fieldname": "itag_column_break_bom_2",
				"fieldtype": "Column Break",
				"insert_after": "itag_applicable_eco",
			},
			{
				"fieldname": "itag_effective_from",
				"fieldtype": "Date",
				"label": "Effective From",
				"insert_after": "itag_column_break_bom_2",
			},
			{
				"fieldname": "itag_effective_to",
				"fieldtype": "Date",
				"label": "Effective To",
				"insert_after": "itag_effective_from",
			},
			{
				"fieldname": "itag_classification_section",
				"fieldtype": "Section Break",
				"label": "Classification",
				"insert_after": "itag_effective_to",
			},
			{
				"fieldname": "itag_design_standard",
				"fieldtype": "Data",
				"label": "Design Standard",
				"insert_after": "itag_classification_section",
			},
			{
				"fieldname": "itag_customer_specification",
				"fieldtype": "Data",
				"label": "Customer Specification",
				"insert_after": "itag_design_standard",
			},
			{
				"fieldname": "itag_column_break_bom_3",
				"fieldtype": "Column Break",
				"insert_after": "itag_customer_specification",
			},
			{
				"fieldname": "itag_change_classification",
				"fieldtype": "Select",
				"label": "Change Classification",
				"options": "\nRoutine\nSafety-Impacting\nCost-Impacting\nCustomer-Specific",
				"insert_after": "itag_column_break_bom_3",
			},
			{
				"fieldname": "itag_obsolescence_status",
				"fieldtype": "Select",
				"label": "Obsolescence Status",
				"options": "\nActive\nObsolete",
				"default": "Active",
				"insert_after": "itag_change_classification",
			},
			{
				"fieldname": "itag_release_readiness_status",
				"fieldtype": "Select",
				"label": "Release Readiness Status",
				"options": "\nNot Ready\nReady\nException",
				"default": "Not Ready",
				"read_only": 1,
				"description": "Set by Build ITAG-0.4.0 Task 5's release-readiness validation service. Not editable directly.",
				"insert_after": "itag_obsolescence_status",
			},
		]
	}


def sync_custom_fields():
	create_custom_fields(get_custom_fields(), update=True)
	create_custom_fields(get_bom_fields(), update=True)
