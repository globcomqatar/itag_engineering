// v15.5.13 #2 (Waheed): a new Item shows Item Type (custom_product_type)
// Critical. Only the value Frappe filled in automatically (blank, the field's
// default or its first option) is replaced; saved Items are left alone. The
// server applies the same rule on insert
// (item_type_options.default_new_item_product_type).
const ITAG_KEEP_PRODUCT_TYPES = ["Critical", "Non-Critical", "Non-Product"];

frappe.ui.form.on("Item", {
	onload(frm) {
		const df = frappe.meta.get_docfield("Item", "custom_product_type", frm.doc.name);
		if (!frm.is_new() || !df || df.fieldtype !== "Select") {
			return;
		}
		const options = (df.options || "").split("\n");
		const value = frm.doc.custom_product_type;
		if (!options.includes("Critical") || ITAG_KEEP_PRODUCT_TYPES.includes(value)) {
			return;
		}
		const automatic = df.default || options[0];
		if (!value || value === automatic) {
			frm.set_value("custom_product_type", "Critical");
		}
	},
});
