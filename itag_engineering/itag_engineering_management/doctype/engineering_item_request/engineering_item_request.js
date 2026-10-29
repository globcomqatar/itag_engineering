// Copyright (c) 2026, Globcom Qatar and contributors
// For license information, please see license.txt

frappe.ui.form.on("Engineering Item Request", {
	setup(frm) {
		// QA v15.5.12 (a): only leaf Item Groups can hold Items.
		frm.set_query("item_group", () => ({ filters: { is_group: 0 } }));
	},
	refresh(frm) {
		setup_create_and_connections(frm);
		warn_on_unknown_master_values(frm);
		const pending = [];
		if (frm.doc.valve_type && !frm._valve_type_name) {
			pending.push(
				frappe.db.get_value("Valve Type", frm.doc.valve_type, "valve_type_name").then((r) => {
					frm._valve_type_name = (r.message && r.message.valve_type_name) || frm.doc.valve_type;
				})
			);
		}
		if (frm.doc.item_code_rule && !frm._rule_series_name) {
			pending.push(
				frappe.db.get_value("Item Code Rule", frm.doc.item_code_rule, "series_name").then((r) => {
					frm._rule_series_name = (r.message && r.message.series_name) || frm.doc.item_code_rule;
				})
			);
		}
		if (!pending.length) {
			show_valve_type_code_note(frm);
			return;
		}
		Promise.all(pending).then(() => show_valve_type_code_note(frm));
	},
	valve_type(frm) {
		if (!frm.doc.valve_type) {
			frm.set_value("item_code_rule", "");
			frm.set_value("code_pattern", "");
			show_valve_type_code_note(frm);
			return;
		}
		frappe.db.get_value("Valve Type", frm.doc.valve_type, ["item_code_rule", "valve_type_name"]).then((r) => {
			const rule = (r.message && r.message.item_code_rule) || "";
			frm._valve_type_name = (r.message && r.message.valve_type_name) || frm.doc.valve_type;
			frm.set_value("item_code_rule", rule).then(() => show_valve_type_code_note(frm));
			if (!rule) {
				frm.set_value("code_pattern", "");
			}
		});
	},
	item_code_rule(frm) {
		if (!frm.doc.item_code_rule) {
			frm.set_value("code_pattern", "");
			show_valve_type_code_note(frm);
			return;
		}
		frappe.db.get_value("Item Code Rule", frm.doc.item_code_rule, ["preview_template", "series_name"]).then((r) => {
			frm._rule_series_name = (r.message && r.message.series_name) || frm.doc.item_code_rule;
			frm.set_value("code_pattern", (r.message && r.message.preview_template) || "").then(() => {
				show_valve_type_code_note(frm);
			});
		});
	},
});

function show_valve_type_code_note(frm) {
	if (frm.doc.created_item) {
		frm.set_intro("");
		return;
	}
	if (!frm.doc.valve_type) {
		frm.set_intro(
			__(
				"Select a Valve Type. The Item Code Rule on that Valve Type supplies the pattern, for example Tag Plate uses 530-#####."
			),
			"blue"
		);
		return;
	}
	const valve_label = frm._valve_type_name || frm.doc.valve_type;
	if (!frm.doc.item_code_rule || !frm.doc.code_pattern) {
		frm.set_intro(
			__(
				"Valve Type {0} has no Item Code Rule. Open that Valve Type and set Item Code Series there.",
				[valve_label]
			),
			"orange"
		);
		return;
	}
	const rule_label = frm._rule_series_name || frm.doc.item_code_rule;
	frm.set_intro(
		__(
			"Item code comes from Item Code Rule {0} ({1}), selected by Valve Type {2}. Submit creates the Item with the next number from that rule.",
			[rule_label, frm.doc.code_pattern, valve_label]
		),
		"green"
	);
}

// fix9 (Waheed, 29-Oct-2026): Create -> Engineering Drawing / BOM from a
// submitted request with an enabled Item; one of each per request.
// Connections rows for Product Revision / Engineering Release open the
// list filtered by item = created_item.
const FIX9_ITEM_KEYED = ["Product Revision", "Engineering Release"];

function setup_create_and_connections(frm) {
	if (frm.dashboard && !frm.dashboard._fix9_patched) {
		const original = frm.dashboard.get_document_filter.bind(frm.dashboard);
		frm.dashboard.get_document_filter = (doctype) =>
			FIX9_ITEM_KEYED.includes(doctype) ? { item: frm.doc.created_item || "__none__" } : original(doctype);
		frm.dashboard._fix9_patched = true;
	}
	if (frm.doc.docstatus !== 1 || !frm.doc.created_item) return;
	frappe.call({
		method: "frappe.client.get_value",
		args: { doctype: "Item", filters: { name: frm.doc.created_item }, fieldname: "disabled" },
	}).then((r) => {
		if (r.message && cint(r.message.disabled)) {
			frm.set_intro(__("Item {0} is disabled, so Create is not available.", [frm.doc.created_item]), "orange");
			return;
		}
		const targets = [
			["Engineering Drawing", "item_request", "make_engineering_drawing"],
			["BOM", "itag_item_request", "make_bom"],
		];
		targets.forEach(([doctype, field, method]) => {
			frappe.db.count(doctype, { filters: { [field]: frm.doc.name, docstatus: ["<", 2] } }).then((n) => {
				if (n) return; // one of each per request
				frm.add_custom_button(
					__(doctype),
					() =>
						frappe.model.open_mapped_doc({
							method: "itag_engineering.itag_engineering_management.item_request_links." + method,
							frm: frm,
						}),
					__("Create")
				);
			});
		});
	});
}

// v15.5.13 #6 (EIR-00005-1): a value typed into Nominal Size, Pressure Class
// or Body Material that is not in its list is cleared by the link check and
// the old value stays. Say so, so the user adds it (Engineering User can
// create these values) and selects it, instead of saving silently.
const MASTER_VALUE_FIELDS = {
	nominal_size: "ITAG Nominal Size",
	pressure_class: "ITAG Pressure Class",
	body_material: "ITAG Body Material",
};

function warn_on_unknown_master_values(frm) {
	Object.entries(MASTER_VALUE_FIELDS).forEach(([fieldname, doctype]) => {
		const field = frm.fields_dict[fieldname];
		if (!field || !field.$input || field.$input.data("itag-master-warn")) {
			return;
		}
		field.$input.data("itag-master-warn", true);
		field.$input.on("blur", () => {
			const typed = (field.$input.val() || "").trim();
			setTimeout(() => {
				if (!typed || frm.doc[fieldname] === typed) {
					return;
				}
				frappe.db.exists(doctype, typed).then((exists) => {
					if (exists) {
						return;
					}
					frappe.show_alert(
						{
							message: __(
								"{0} {1} was not found, so it was not kept. Use Create a new {0} in the list to add it, then select it.",
								[__(field.df.label), frappe.utils.escape_html(typed)]
							),
							indicator: "orange",
						},
						10
					);
				});
			}, 500);
		});
	});
}
