// Copyright (c) 2026, Globcom Qatar and contributors
// For license information, please see license.txt

// The Engineering Drawing workflow was removed. release_status now moves one
// step at a time through drawing_service.advance_drawing(), which enforces the
// order and the role. The checks here only decide which buttons to show.
const DRAWING_SERVICE = "itag_engineering.itag_engineering_management.drawing_service";

// Next steps from each status, and the role needed to move into each one.
const DRAWING_NEXT_STEPS = {
	Draft: ["Engineering Review"],
	"Engineering Review": ["Checked"],
	Checked: ["Approved"],
	Approved: ["Released"],
	Released: ["Superseded", "Obsolete"],
	Superseded: ["Obsolete"],
};
const DRAWING_STEP_ROLES = {
	"Engineering Review": ["Engineering User", "Engineering Manager"],
	Checked: ["Engineering Manager"],
	Approved: ["Engineering Manager"],
	Released: ["Engineering Manager"],
	Superseded: ["Engineering Manager"],
	Obsolete: ["Engineering Manager"],
};

frappe.ui.form.on("Engineering Drawing", {
	refresh(frm) {
		if (frm.is_new()) {
			return;
		}
		(DRAWING_NEXT_STEPS[frm.doc.release_status] || []).forEach((next_state) => {
			if (!DRAWING_STEP_ROLES[next_state].some((role) => frappe.user.has_role(role))) {
				return;
			}
			frm.add_custom_button(
				__("Move to {0}", [__(next_state)]),
				() => {
					frappe.confirm(
						__("Move this drawing from {0} to {1}?", [
							__(frm.doc.release_status),
							__(next_state),
						]),
						() => {
							frappe
								.call({
									method: `${DRAWING_SERVICE}.advance_drawing_api`,
									args: { drawing_name: frm.doc.name, to_state: next_state },
									freeze: true,
									freeze_message: __("Updating status..."),
								})
								.then((r) => {
									if (r.message) {
										frm.reload_doc();
									}
								});
						}
					);
				},
				__("Actions")
			);
		});
	},
});
