// Copyright (c) 2026, Globcom Qatar and contributors
// For license information, please see license.txt

frappe.ui.form.on("Product Revision", {
	refresh(frm) {
		// F3: Cancel marks this revision Superseded. BOMs, Engineering Releases
		// and Work Orders that point at it keep the link as history and are
		// never offered for "Cancel All".
		frm.ignore_doctypes_on_cancel_all = (frm.doc.__onload || {}).ignore_doctypes_on_cancel || [];
	},
});
