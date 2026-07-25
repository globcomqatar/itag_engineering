// Copyright (c) 2026, Globcom Qatar and contributors
// For license information, please see license.txt

// Injected into the core ERPNext "BOM" doctype via hooks.py's doctype_js
// (BOM is not itag_engineering's own DocType, so this lives here rather
// than in a doctype/ folder - core files are never modified directly).
//
// bom_readiness_service.evaluate_bom_readiness_api() (roadmap Section 12.4)
// had no Desk UI trigger at all - the only way to populate
// itag_release_readiness_status was a direct API/console call. Same
// missing-button gap as engineering_release.js/engineering_change_order.js,
// fixed the same way.
frappe.ui.form.on("BOM", {
	refresh(frm) {
		// Readiness is meaningful on both a Draft (pre-submission sanity
		// check) and a Submitted/active BOM (the state release_service.py's
		// _check_bom_release_ready() actually reads at Engineering Release
		// time) - only a Cancelled BOM has nothing left to evaluate.
		if (frm.doc.docstatus === 2) {
			return;
		}
		frm.add_custom_button(
			__("Evaluate Release Readiness"),
			() => {
				frappe.call({
					method: "itag_engineering.itag_engineering_management.bom_readiness_service.evaluate_bom_readiness_api",
					args: { bom_name: frm.doc.name },
					freeze: true,
					freeze_message: __("Evaluating Release Readiness..."),
				}).then((r) => {
					if (!r.message) {
						return;
					}
					const result = r.message.data;
					if (result.ready) {
						frappe.msgprint({
							title: __("Ready"),
							indicator: "green",
							message: __("This BOM meets every release-readiness criterion."),
						});
					} else {
						frappe.msgprint({
							title: __("Exception"),
							indicator: "red",
							message:
								__("This BOM is not release-ready:") +
								"<ul><li>" +
								result.exceptions.map((e) => frappe.utils.escape_html(e)).join("</li><li>") +
								"</li></ul>",
						});
					}
					frm.reload_doc();
				});
			},
			__("Actions")
		);
	},
});
