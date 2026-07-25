// Copyright (c) 2026, Globcom Qatar and contributors
// For license information, please see license.txt

frappe.ui.form.on("Engineering Change Order", {
	refresh(frm) {
		// approval_steps is read_only:1 (materialized display only) - there
		// was no way to ever mark a row Approved/Rejected through the Desk,
		// even though eco_service.approve_or_reject_workflow_step() already
		// existed. Doesn't block ECO's own workflow transitions (no
		// server-side guard requires approval_steps to be Approved before
		// ECO can reach Closed, unlike Engineering Release's
		// _validate_all_approval_steps_approved()), but the row could never
		// be actioned from the Desk regardless. Same pattern as
		// engineering_release.js's per-row "Approve Step" buttons.
		(frm.doc.approval_steps || [])
			.filter((step) => step.status === "Pending")
			.forEach((step) => {
				frm.add_custom_button(
					__("Approve Step: {0}", [step.discipline]),
					() => {
						frappe.call({
							method: "itag_engineering.itag_engineering_management.eco_service.approve_or_reject_workflow_step_api",
							args: { eco_name: frm.doc.name, step_idx: step.idx, approve: true },
							freeze: true,
							freeze_message: __("Approving Step..."),
						}).then((r) => {
							if (!r.message) {
								return;
							}
							frappe.msgprint({
								title: __("Step Approved"),
								indicator: "green",
								message: __("Approval step {0} ({1}) has been approved.", [
									step.sequence,
									step.discipline,
								]),
							});
							frm.reload_doc();
						});
					},
					__("Approval Steps")
				);
			});

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
