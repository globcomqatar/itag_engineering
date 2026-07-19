// Copyright (c) 2026, Globcom Qatar and contributors
// For license information, please see license.txt

frappe.ui.form.on("Engineering Item Request", {
	refresh(frm) {
		// The workflow's own "Create Item" transition (Approved -> Item
		// Created) only flips workflow_state - it does not run the real
		// eir_service.create_item_from_eir() logic (Item Code reservation,
		// Item creation, reservation consumption). Give Approvers a single,
		// correctly-wired action instead. The server-side guard in
		// engineering_item_request.py's validate() blocks the raw workflow
		// transition if it is used regardless, so this is a UX convenience,
		// not the enforcement point.
		if (frm.doc.workflow_state === "Approved" && !frm.doc.created_item) {
			frm.add_custom_button(
				__("Create Item"),
				() => {
					frappe.confirm(
						__("This will reserve an Item Code (if not already reserved), create the Item, and move this request to Item Created. Continue?"),
						() => {
							// Not frm.call: create_item_from_eir_api is a
							// standalone whitelisted module function, not a
							// method on this DocType's controller, so a plain
							// frappe.call keeps this a simple RPC instead of
							// frm.call's doc-bound run_doc_method path.
							frappe.call({
								method: "itag_engineering.itag_engineering_management.eir_service.create_item_from_eir_api",
								args: { eir_name: frm.doc.name },
								freeze: true,
								freeze_message: __("Creating Item..."),
							}).then((r) => {
								if (!r.message) {
									return;
								}
								frappe.msgprint({
									title: __("Item Created"),
									indicator: "green",
									message: __("Item {0} has been created and linked to this request.", [
										frappe.utils.escape_html(r.message.data.item_code),
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
