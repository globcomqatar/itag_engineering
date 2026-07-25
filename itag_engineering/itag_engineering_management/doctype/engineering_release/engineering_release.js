// Copyright (c) 2026, Globcom Qatar and contributors
// For license information, please see license.txt

frappe.ui.form.on("Engineering Release", {
	refresh(frm) {
		// The workflow's own "Release for Production" transition only flips
		// release_status - it does not run the real
		// release_service.submit_engineering_release() logic (package
		// re-validation, approval-step completion check, release_checksum
		// computation, prior-release supersession, distribution list,
		// notifications - roadmap Section 13.6). A server-side guard in
		// engineering_release.py blocks the raw transition if it is ever
		// used regardless, so this is a UX convenience, not the enforcement
		// point - same pattern as engineering_item_request.js's "Create
		// Item" button and engineering_change_request.js's "Accept for ECO"
		// button.
		// Named distinctly from the raw workflow's own "Release for
		// Production" transition action (same state, same label would
		// otherwise exist twice in the same Actions dropdown - Frappe's
		// add_inner_button() silently skips adding a second entry with an
		// identical label, so a real click can land on whichever the
		// workflow engine's own render pass happened to add, not
		// necessarily this button's handler).
		// release_status is Engineering Release's actual workflow-state
		// field (workflow_state_field: "release_status" in the Workflow
		// fixture) - this DocType has no plain workflow_state field at all,
		// unlike every other workflow-bearing doctype in this app.
		if (frm.doc.release_status === "Engineering Approved" && !frm.doc.release_checksum) {
			frm.add_custom_button(
				__("Submit Release for Production"),
				() => {
					frappe.confirm(
						__("This will re-validate the release package, confirm all required approvals are complete, compute the release checksum, supersede the prior release where applicable, and move this release to Released for Production. Continue?"),
						() => {
							frappe.call({
								method: "itag_engineering.itag_engineering_management.release_service.submit_engineering_release_api",
								args: { release_name: frm.doc.name },
								freeze: true,
								freeze_message: __("Releasing for Production..."),
							}).then((r) => {
								if (!r.message) {
									return;
								}
								frappe.msgprint({
									title: __("Released for Production"),
									indicator: "green",
									message: __("Engineering Release {0} has been released for production.", [
										frappe.utils.escape_html(frm.doc.name),
									]),
								});
								frm.reload_doc();
							});
						}
					);
				},
				__("Actions")
			);
		}

		// approval_steps is read_only:1 (materialized display only) - there
		// was no way to ever mark a row Approved/Rejected through the Desk
		// (release_service.approve_or_reject_release_step() added
		// specifically to close this gap, mirroring eco_service.py's
		// identical, already-documented gap for Engineering Change Order).
		// One button per still-Pending row, since a release can resolve
		// more than one required discipline.
		(frm.doc.approval_steps || [])
			.filter((step) => step.status === "Pending")
			.forEach((step) => {
				frm.add_custom_button(
					__("Approve Step: {0}", [step.discipline]),
					() => {
						frappe.call({
							method: "itag_engineering.itag_engineering_management.release_service.approve_or_reject_release_step_api",
							args: { release_name: frm.doc.name, step_idx: step.idx, approve: true },
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

		if (!frm.doc.approval_matrix) {
			frm.add_custom_button(
				__("Resolve Approval Matrix"),
				() => {
					frappe.call({
						method: "itag_engineering.itag_engineering_management.release_service.resolve_release_approval_matrix_api",
						args: { release_name: frm.doc.name },
						freeze: true,
						freeze_message: __("Resolving Approval Matrix..."),
					}).then((r) => {
						if (!r.message) {
							return;
						}
						frappe.msgprint({
							title: __("Approval Matrix Resolved"),
							indicator: "green",
							message: __("Required approval disciplines have been resolved for this release."),
						});
						frm.reload_doc();
					});
				},
				__("Actions")
			);
		}
	},
});
