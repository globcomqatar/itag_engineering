// Copyright (c) 2026, Globcom Qatar and contributors
// For license information, please see license.txt

frappe.ui.form.on("Engineering Item Request", {
	refresh(frm) {
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
