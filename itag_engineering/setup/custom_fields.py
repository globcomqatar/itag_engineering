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
				"fieldtype": "Link",
				"options": "Product Family",
				"insert_after": "itag_engineering_classification",
			},
			{
				"fieldname": "itag_valve_type",
				"label": "Valve Type",
				"fieldtype": "Link",
				"options": "Valve Type",
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
				"fieldtype": "Link",
				"options": "Engineering Release",
				"label": "Engineering Release",
				"description": "Converted from a Data forward-reference placeholder to a real Link by patches.v0_5.convert_engineering_release_placeholder_fields now that Engineering Release (Build ITAG-0.5.0) exists. This getter must declare the CURRENT correct schema (Link) - the one-time patch only migrates data on already-provisioned sites; a fresh install/migrate never runs the patch's guard branch and must get the right fieldtype straight from here.",
				"insert_after": "itag_release_section",
			},
			{
				"fieldname": "itag_applicable_eco",
				"fieldtype": "Link",
				"options": "Engineering Change Order",
				"label": "Applicable ECO",
				"description": "Converted from a Data forward-reference placeholder to a real Link by patches.v0_6.convert_applicable_eco_placeholder_fields now that Engineering Change Order (Build ITAG-0.6.0) exists. See itag_engineering_release's own description above for why this getter declares Link directly rather than relying solely on the patch.",
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


def get_routing_fields():
	return {
		"Routing": [
			{
				"fieldname": "itag_engineering_section",
				"fieldtype": "Section Break",
				"label": "Engineering",
				# Verified via routing.json and a live tabDocField query: Routing has
				# only routing_name (Data), disabled (Check), and operations (Table).
				# "disabled" is the last non-table field, so it is a safe anchor.
				"insert_after": "disabled",
			},
			{
				"fieldname": "itag_routing_revision",
				"fieldtype": "Data",
				"label": "Routing Revision",
				"insert_after": "itag_engineering_section",
			},
			{
				"fieldname": "itag_product_revision",
				"fieldtype": "Link",
				"label": "Product Revision",
				"options": "Product Revision",
				"insert_after": "itag_routing_revision",
			},
			{
				"fieldname": "itag_column_break_routing_1",
				"fieldtype": "Column Break",
				"insert_after": "itag_product_revision",
			},
			{
				"fieldname": "itag_engineering_release",
				"fieldtype": "Link",
				"options": "Engineering Release",
				"label": "Engineering Release",
				"description": "Converted from a Data forward-reference placeholder to a real Link by patches.v0_5.convert_engineering_release_placeholder_fields now that Engineering Release (Build ITAG-0.5.0) exists. This getter must declare the CURRENT correct schema (Link) - see BOM's own itag_engineering_release field for the full explanation.",
				"insert_after": "itag_column_break_routing_1",
			},
			{
				"fieldname": "itag_applicable_eco",
				"fieldtype": "Link",
				"options": "Engineering Change Order",
				"label": "Applicable ECO",
				"description": "Converted from a Data forward-reference placeholder to a real Link by patches.v0_6.convert_applicable_eco_placeholder_fields now that Engineering Change Order (Build ITAG-0.6.0) exists.",
				"insert_after": "itag_engineering_release",
			},
			{
				"fieldname": "itag_effective_from",
				"fieldtype": "Date",
				"label": "Effective From",
				"insert_after": "itag_applicable_eco",
			},
			{
				"fieldname": "itag_effective_to",
				"fieldtype": "Date",
				"label": "Effective To",
				"insert_after": "itag_effective_from",
			},
			{
				"fieldname": "itag_release_status",
				"fieldtype": "Select",
				"label": "Release Status",
				"options": "\nDraft\nApproved\nReleased\nObsolete",
				"default": "Draft",
				"insert_after": "itag_effective_to",
			},
		]
	}


def get_bom_operation_fields():
	return {
		"BOM Operation": [
			{
				"fieldname": "itag_engineering_section",
				"fieldtype": "Section Break",
				"label": "Engineering Control",
				# Verified via bom_operation.json and a live tabDocField query:
				# "sequence_id" exists on BOM Operation (Int field), and both
				# BOM.operations and Routing.operations point their `options` at
				# "BOM Operation" - confirming this is the single shared child
				# doctype. Anchor confirmed correct as proposed in the brief.
				"insert_after": "sequence_id",
			},
			{
				"fieldname": "itag_operation_revision",
				"fieldtype": "Data",
				"label": "Operation Revision",
				"insert_after": "itag_engineering_section",
			},
			{
				"fieldname": "itag_drawing_reference",
				"fieldtype": "Link",
				"label": "Drawing Reference",
				"options": "Engineering Drawing",
				"insert_after": "itag_operation_revision",
			},
			{
				"fieldname": "itag_column_break_bomop_1",
				"fieldtype": "Column Break",
				"insert_after": "itag_drawing_reference",
			},
			{
				"fieldname": "itag_required_skill",
				"fieldtype": "Data",
				"label": "Required Skill",
				"insert_after": "itag_column_break_bomop_1",
			},
			{
				"fieldname": "itag_required_tool_or_fixture",
				"fieldtype": "Data",
				"label": "Required Tool or Fixture",
				"insert_after": "itag_required_skill",
			},
			{
				"fieldname": "itag_setup_time",
				"fieldtype": "Float",
				"label": "Setup Time (Minutes)",
				"insert_after": "itag_required_tool_or_fixture",
			},
			{
				"fieldname": "itag_instructions_section",
				"fieldtype": "Section Break",
				"label": "Instructions",
				"insert_after": "itag_setup_time",
			},
			{
				"fieldname": "itag_work_instruction",
				"fieldtype": "Text",
				"label": "Work Instruction",
				"insert_after": "itag_instructions_section",
			},
			{
				"fieldname": "itag_safety_instruction",
				"fieldtype": "Small Text",
				"label": "Safety Instruction",
				"insert_after": "itag_work_instruction",
			},
			{
				"fieldname": "itag_quality_section",
				"fieldtype": "Section Break",
				"label": "Quality Control Points",
				"insert_after": "itag_safety_instruction",
			},
			{
				"fieldname": "itag_hold_point",
				"fieldtype": "Check",
				"label": "Hold Point",
				"insert_after": "itag_quality_section",
			},
			{
				"fieldname": "itag_witness_point",
				"fieldtype": "Check",
				"label": "Witness Point",
				"insert_after": "itag_hold_point",
			},
			{
				"fieldname": "itag_column_break_bomop_2",
				"fieldtype": "Column Break",
				"insert_after": "itag_witness_point",
			},
			{
				"fieldname": "itag_inspection_requirement",
				"fieldtype": "Small Text",
				"label": "Inspection Requirement",
				"insert_after": "itag_column_break_bomop_2",
			},
			{
				"fieldname": "itag_acceptance_criteria",
				"fieldtype": "Small Text",
				"label": "Acceptance Criteria",
				"insert_after": "itag_inspection_requirement",
			},
		]
	}


def get_work_order_baseline_fields():
	return {
		"Work Order": [
			{
				# insert_after intentionally omitted: this environment has no live
				# bench to confirm Work Order's own last standard fieldname against
				# (Build 0.5.0's plan explicitly calls for that live check before
				# writing an anchor). Omitting insert_after is a supported
				# create_custom_fields() call - the field is appended at the end of
				# the doctype's field list - and is safe regardless of Work Order's
				# exact standard field layout. Confirm a real anchor against
				# `frappe.get_meta("Work Order")` on the live bench and set
				# insert_after explicitly before/at first migrate.
				"fieldname": "itag_engineering_baseline_tab",
				"fieldtype": "Tab Break",
				"label": "Engineering Baseline",
			},
			{
				"fieldname": "itag_engineering_release",
				"fieldtype": "Link",
				"label": "Engineering Release",
				"options": "Engineering Release",
				"read_only": 1,
				"description": "Frozen by Build ITAG-0.5.0 at submission (freeze_baseline_before_submit). Not editable.",
				"insert_after": "itag_engineering_baseline_tab",
			},
			{
				"fieldname": "itag_product_revision",
				"fieldtype": "Link",
				"label": "Product Revision",
				"options": "Product Revision",
				"read_only": 1,
				"insert_after": "itag_engineering_release",
			},
			{
				"fieldname": "itag_drawing_revision",
				"fieldtype": "Link",
				"label": "Drawing Revision",
				"options": "Engineering Drawing",
				"read_only": 1,
				"insert_after": "itag_product_revision",
			},
			{
				"fieldname": "itag_column_break_wobaseline_1",
				"fieldtype": "Column Break",
				"insert_after": "itag_drawing_revision",
			},
			{
				"fieldname": "itag_bom_revision",
				"fieldtype": "Link",
				"label": "BOM Revision",
				"options": "BOM",
				"read_only": 1,
				"insert_after": "itag_column_break_wobaseline_1",
			},
			{
				"fieldname": "itag_routing_revision",
				"fieldtype": "Link",
				"label": "Routing Revision",
				"options": "Routing",
				"read_only": 1,
				"insert_after": "itag_bom_revision",
			},
			{
				"fieldname": "itag_inspection_plan_revision",
				"fieldtype": "Link",
				"label": "Inspection Plan Revision",
				"options": "Engineering Inspection Plan",
				"read_only": 1,
				"insert_after": "itag_routing_revision",
			},
		]
	}


def get_work_order_continuation_fields():
	"""Build ITAG-0.9.0 Task 3 (roadmap Section 19.6 step 10). Confirmed via
	a grep of this app's own custom_fields.py (the only place this app adds
	Work Order fields) that neither field existed before this build."""
	return {
		"Work Order": [
			{
				"fieldname": "itag_original_work_order",
				"fieldtype": "Link",
				"label": "Original Work Order",
				"options": "Work Order",
				"read_only": 1,
				"description": "Set on a successor Work Order by continuation_service.create_successor_work_order() - the Work Order this one continues production from under a new Engineering Release.",
				"insert_after": "itag_inspection_plan_revision",
			},
			{
				"fieldname": "itag_successor_work_order",
				"fieldtype": "Link",
				"label": "Successor Work Order",
				"options": "Work Order",
				"read_only": 1,
				"description": "Set on the ORIGINAL Work Order once a Production Change Continuation creates its successor.",
				"insert_after": "itag_original_work_order",
			},
		]
	}


def get_wip_traceability_fields():
	"""Build ITAG-0.10.0 Task 1 (roadmap Section 21.3).

	Only Serial No, Batch, and Quality Inspection get new custom fields.
	Stock Entry, Purchase Order, Purchase Receipt, Sales Order, and
	Delivery Note deliberately do NOT - each of those already carries its
	own item_code/serial_no/batch_no fields, and traceability_service.py
	(Build ITAG-0.10.0 Task 4) reaches them by joining on THOSE existing
	fields against Serial No/Batch's new itag_* fields below, exactly the
	same join-not-duplicate-field approach Build ITAG-0.7.0's
	impact_analysis_service.py already established for Purchase Order
	Item/Sales Order Item/Delivery Note Item. Adding a redundant
	itag_wip_unit/itag_eco field to all 5 of those doctypes would be pure
	duplication with no new traceability path it unlocks.

	insert_after is intentionally omitted for the same reason Build
	ITAG-0.5.0's work_order_baseline_fields omits it: no live bench in this
	session to confirm Serial No/Batch/Quality Inspection's own last
	standard fieldname against frappe.get_meta(...). Confirm real anchors
	before/at first migrate on the live bench.
	"""
	return {
		"Serial No": [
			{
				"fieldname": "itag_engineering_baseline_tab",
				"fieldtype": "Tab Break",
				"label": "Engineering Baseline",
			},
			{
				"fieldname": "itag_engineering_release",
				"fieldtype": "Link",
				"label": "Engineering Release",
				"options": "Engineering Release",
				"description": "This serial's OWN baseline reference, independent of whatever Work Order produced it - a serial's identity can outlive the Work Order record's own convenience.",
				"insert_after": "itag_engineering_baseline_tab",
			},
			{
				"fieldname": "itag_product_revision",
				"fieldtype": "Link",
				"label": "Product Revision",
				"options": "Product Revision",
				"insert_after": "itag_engineering_release",
			},
			{
				"fieldname": "itag_drawing_revision",
				"fieldtype": "Link",
				"label": "Drawing Revision",
				"options": "Engineering Drawing",
				"insert_after": "itag_product_revision",
			},
			{
				"fieldname": "itag_column_break_serial_1",
				"fieldtype": "Column Break",
				"insert_after": "itag_drawing_revision",
			},
			{
				"fieldname": "itag_bom_revision",
				"fieldtype": "Link",
				"label": "BOM Revision",
				"options": "BOM",
				"insert_after": "itag_column_break_serial_1",
			},
			{
				"fieldname": "itag_wip_unit",
				"fieldtype": "Link",
				"label": "WIP Unit",
				"options": "WIP Unit Register",
				"insert_after": "itag_bom_revision",
			},
		],
		"Batch": [
			{
				"fieldname": "itag_engineering_baseline_tab",
				"fieldtype": "Tab Break",
				"label": "Engineering Baseline",
			},
			{
				"fieldname": "itag_heat_number",
				"fieldtype": "Data",
				"label": "Heat Number",
				"description": "Heat-number tracking modeled as a Batch/Serial No extension field (Decision Log #6), not a separate DocType.",
				"insert_after": "itag_engineering_baseline_tab",
			},
			{
				"fieldname": "itag_material_certificate",
				"fieldtype": "Attach",
				"label": "Material Certificate",
				"insert_after": "itag_heat_number",
			},
			{
				"fieldname": "itag_column_break_batch_1",
				"fieldtype": "Column Break",
				"insert_after": "itag_material_certificate",
			},
			{
				"fieldname": "itag_drawing_revision",
				"fieldtype": "Link",
				"label": "Drawing Revision",
				"options": "Engineering Drawing",
				"insert_after": "itag_column_break_batch_1",
			},
			{
				"fieldname": "itag_bom_revision",
				"fieldtype": "Link",
				"label": "BOM Revision",
				"options": "BOM",
				"insert_after": "itag_drawing_revision",
			},
		],
		"Quality Inspection": [
			{
				"fieldname": "itag_wip_unit",
				"fieldtype": "Link",
				"label": "WIP Unit",
				"options": "WIP Unit Register",
			},
			{
				"fieldname": "itag_eco",
				"fieldtype": "Link",
				"label": "Engineering Change Order",
				"options": "Engineering Change Order",
				"insert_after": "itag_wip_unit",
			},
		],
	}


def sync_custom_fields():
	create_custom_fields(get_custom_fields(), update=True)
	create_custom_fields(get_bom_fields(), update=True)
	create_custom_fields(get_routing_fields(), update=True)
	create_custom_fields(get_bom_operation_fields(), update=True)
	create_custom_fields(get_work_order_baseline_fields(), update=True)
	create_custom_fields(get_work_order_continuation_fields(), update=True)
	create_custom_fields(get_wip_traceability_fields(), update=True)
