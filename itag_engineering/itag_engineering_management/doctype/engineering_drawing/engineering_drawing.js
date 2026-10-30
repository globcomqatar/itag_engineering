// Copyright (c) 2026, Globcom Qatar and contributors
// For license information, please see license.txt

// v15.5.12 #6 (Waheed): Create -> Engineering Release / BOM / Engineering
// Change Order on a submitted drawing. A button is shown only when the user
// can create that doctype; the server checks the same permission.
const DRAWING_CREATE_TARGETS = [
	["Engineering Release", "make_engineering_release"],
	["BOM", "make_bom"],
	["Engineering Change Order", "make_engineering_change_order"],
];

frappe.ui.form.on("Engineering Drawing", {
	refresh(frm) {
		if (frm.doc.docstatus !== 1) return;
		DRAWING_CREATE_TARGETS.forEach(([doctype, method]) => {
			if (!frappe.model.can_create(doctype)) return;
			frm.add_custom_button(
				__(doctype),
				() =>
					frappe.model.open_mapped_doc({
						method: "itag_engineering.itag_engineering_management.drawing_links." + method,
						frm: frm,
					}),
				__("Create")
			);
		});
	},
});
