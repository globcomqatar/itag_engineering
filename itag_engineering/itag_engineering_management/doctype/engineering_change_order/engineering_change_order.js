// Copyright (c) 2026, Globcom Qatar and contributors
// For license information, please see license.txt

frappe.ui.form.on("Engineering Change Order", {
	refresh(frm) {
		// eco_service.resolve_eco_approval_disciplines() - which sets
		// approval_matrix/requires_cost_review/requires_customer_review,
		// all read_only fields the Production Review -> Cost Review /
		// Customer Approval conditional workflow transitions branch on -
		// had no Desk UI trigger at all before this button. Same pattern as
		// engineering_release.js's "Resolve Approval Matrix" button.
		if (!frm.doc.approval_matrix) {
			frm.add_custom_button(
				__("Resolve Approval Disciplines"),
				() => {
					frappe.call({
						method: "itag_engineering.itag_engineering_management.eco_service.resolve_eco_approval_disciplines_api",
						args: { eco_name: frm.doc.name },
						freeze: true,
						freeze_message: __("Resolving Approval Disciplines..."),
					}).then((r) => {
						if (!r.message) {
							return;
						}
						frappe.msgprint({
							title: __("Approval Disciplines Resolved"),
							indicator: "green",
							message: __("Required approval disciplines have been resolved for this change order."),
						});
						frm.reload_doc();
					});
				},
				__("Actions")
			);
		}
	},
});
