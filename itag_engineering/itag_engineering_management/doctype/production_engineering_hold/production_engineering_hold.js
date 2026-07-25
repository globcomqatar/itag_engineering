// Copyright (c) 2026, Globcom Qatar and contributors
// For license information, please see license.txt

// hold_service.release_hold_api() had no Desk UI trigger at all - status
// is read_only:1 (like every other computed/service-set field pattern in
// this app), so there was no way to ever release a hold through the
// Desk. Same missing-button gap as engineering_release.js/
// engineering_change_order.js/bom.js, fixed the same way.
frappe.ui.form.on("Production Engineering Hold", {
	refresh(frm) {
		if (frm.doc.status === "Active") {
			frm.add_custom_button(
				__("Release Hold"),
				() => {
					frappe.prompt(
						{
							fieldname: "release_reason",
							label: __("Release Reason"),
							fieldtype: "Small Text",
							reqd: 1,
						},
						(values) => {
							frappe.call({
								method: "itag_engineering.itag_engineering_management.hold_service.release_hold_api",
								args: { hold_name: frm.doc.name, release_reason: values.release_reason },
								freeze: true,
								freeze_message: __("Releasing Hold..."),
							}).then((r) => {
								if (!r.message) {
									return;
								}
								frappe.msgprint({
									title: __("Hold Released"),
									indicator: "green",
									message: __("Production Engineering Hold {0} has been released.", [
										frappe.utils.escape_html(frm.doc.name),
									]),
								});
								frm.reload_doc();
							});
						},
						__("Release Hold"),
						__("Release")
					);
				},
				__("Actions")
			);
		}
	},
});
