// Copyright (c) 2026, Globcom Qatar and contributors
// For license information, please see license.txt

frappe.ui.form.on("Engineering Item Request", {
	refresh(frm) {
		add_review_buttons(frm);
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

// The Engineering Item Request workflow was removed. These buttons call the
// role-gated services in eir_service.py, which enforce the rules. The role and
// state checks here only decide which buttons to show.
const EIR_SERVICE = "itag_engineering.itag_engineering_management.eir_service";
const EIR_OPEN_STATES = ["Draft", "Duplicate Review", "Engineering Review", "Returned for Correction"];

function add_review_buttons(frm) {
	if (frm.is_new() || frm.doc.__islocal) {
		return;
	}
	if (EIR_OPEN_STATES.includes(frm.doc.workflow_state) && frappe.user.has_role("Engineering Manager")) {
		frm.add_custom_button(
			__("Approve"),
			() => {
				frappe.confirm(__("Approve this Engineering Item Request?"), () => {
					frappe
						.call({
							method: `${EIR_SERVICE}.approve_eir_api`,
							args: { eir_name: frm.doc.name },
							freeze: true,
							freeze_message: __("Approving..."),
						})
						.then((r) => {
							if (r.message) {
								frm.reload_doc();
							}
						});
				});
			},
			__("Actions")
		);
		frm.add_custom_button(
			__("Reject"),
			() => {
				frappe.prompt(
					[{ fieldname: "reason", fieldtype: "Small Text", label: __("Reason"), reqd: 1 }],
					(values) => {
						frappe
							.call({
								method: `${EIR_SERVICE}.reject_eir_api`,
								args: { eir_name: frm.doc.name, reason: values.reason },
								freeze: true,
								freeze_message: __("Rejecting..."),
							})
							.then((r) => {
								if (r.message) {
									frm.reload_doc();
								}
							});
					},
					__("Reject Engineering Item Request"),
					__("Reject")
				);
			},
			__("Actions")
		);
	}
	if (
		frm.doc.workflow_state === "Approved" &&
		!frm.doc.created_item &&
		(frappe.user.has_role("Engineering User") || frappe.user.has_role("Engineering Manager"))
	) {
		frm.add_custom_button(
			__("Create Item"),
			() => {
				frappe.confirm(__("Create the Item for this request?"), () => {
					frappe
						.call({
							method: `${EIR_SERVICE}.create_item_from_eir_api`,
							args: { eir_name: frm.doc.name },
							freeze: true,
							freeze_message: __("Creating Item..."),
						})
						.then((r) => {
							if (r.message) {
								frm.reload_doc();
							}
						});
				});
			},
			__("Actions")
		);
	}
}

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
			"Item code comes from Item Code Rule {0} ({1}), selected by Valve Type {2}. Create Item assigns the next number from that rule.",
			[rule_label, frm.doc.code_pattern, valve_label]
		),
		"green"
	);
}
