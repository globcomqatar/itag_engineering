// Copyright (c) 2026, Globcom Qatar and contributors
// For license information, please see license.txt

frappe.ui.form.on("Engineering Change Request", {
	refresh(frm) {
		// The workflow's own "Accept for ECO" transition only flips
		// workflow_state - it does not run the real
		// eco_service.create_eco_from_accepted_ecr() logic (seeding
		// Controlled Changes from this request's affected objects,
		// creating the ECO, linking it back via originating_eco). Give
		// Engineering Managers a single, correctly-wired action instead.
		// The server-side guard in engineering_change_request.py's
		// validate() blocks the raw workflow transition if it is used
		// regardless, so this is a UX convenience, not the enforcement
		// point - same pattern as engineering_item_request.js's
		// "Create Item" button.
		if (frm.doc.workflow_state === "Engineering Review" && !frm.doc.originating_eco) {
			frm.add_custom_button(
				__("Accept for ECO"),
				() => {
					frappe.confirm(
						__("This will create an Engineering Change Order seeded from this request's affected objects and move this request to Accepted for ECO. Continue?"),
						() => {
							frappe.call({
								method: "itag_engineering.itag_engineering_management.eco_service.create_eco_from_accepted_ecr_api",
								args: { ecr_name: frm.doc.name },
								freeze: true,
								freeze_message: __("Creating Engineering Change Order..."),
							}).then((r) => {
								if (!r.message) {
									return;
								}
								frappe.msgprint({
									title: __("Engineering Change Order Created"),
									indicator: "green",
									message: __("Engineering Change Order {0} has been created and linked to this request.", [
										frappe.utils.escape_html(r.message.data.name),
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
	},
});
