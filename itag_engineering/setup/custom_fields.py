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


def sync_custom_fields():
	create_custom_fields(get_custom_fields(), update=True)
