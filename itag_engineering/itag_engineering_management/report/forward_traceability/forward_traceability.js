// Copyright (c) 2026, Globcom Qatar and contributors
// For license information, please see license.txt

// forward_traceability.py's execute() requires an `identity` filter and
// silently returns no rows without one - but no report .js existed to
// ever surface that filter field in the Desk. Same missing-UI-trigger gap
// as backward_traceability.js, fixed the same way. Plain Data field, not
// a Link, since traceability_service.forward_traceability() accepts a
// heat number, Batch, Serial No, WIP Unit Register, or drawing revision -
// five different doctypes, no single Link options value would fit.
// (execute() never forwards include_recall_population_check to the
// service call, so that parameter is intentionally left as backend-only,
// not exposed as a second filter here.)
frappe.query_reports["Forward Traceability"] = {
	filters: [
		{
			fieldname: "identity",
			label: __("Heat No / Batch / Serial No / WIP Unit / Drawing Revision"),
			fieldtype: "Data",
			reqd: 1,
		},
	],
};
