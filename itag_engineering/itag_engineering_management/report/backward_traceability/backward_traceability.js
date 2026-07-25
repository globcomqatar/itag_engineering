// Copyright (c) 2026, Globcom Qatar and contributors
// For license information, please see license.txt

// backward_traceability.py's execute() requires a `serial_or_wip_unit`
// filter and silently returns no rows without one - but no report .js
// existed to ever surface that filter field in the Desk, so this report
// was permanently blank for any real user (same missing-UI-trigger gap as
// engineering_release.js/bom.js/production_engineering_hold.js, fixed the
// same way). Plain Data field, not a Link, since traceability_service.
// backward_traceability() accepts either a Serial No or a WIP Unit
// Register name.
frappe.query_reports["Backward Traceability"] = {
	filters: [
		{
			fieldname: "serial_or_wip_unit",
			label: __("Serial No / WIP Unit"),
			fieldtype: "Data",
			reqd: 1,
		},
	],
};
