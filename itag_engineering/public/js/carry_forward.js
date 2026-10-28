// Copyright (c) 2026, Globcom Qatar and contributors
// For license information, please see license.txt

// Later documents keep the request classification visible. The Item holds
// the stored copy. Blank matching fields, including the drawing number and
// the current product revision, are filled from that Item. A value the user
// already typed is left as it is. WIP Unit Register is not filled here; it
// copies the Work Order baseline when it is created.

const CARRY_ITEM_FIELD = {
	"Engineering Drawing": "related_item",
	"Technical Specification": "related_item",
	"Product Revision": "item",
	"Engineering Release": "item",
	"Engineering Inspection Plan": "related_item",
	"Engineering Change Request": "affected_item",
	"Material Disposition": "item",
	BOM: "item",
	"Work Order": "production_item",
};

const CARRY_LABELS = [
	["item_category", __("Item Category")],
	["item_type", __("Item Type")],
	["product_family", __("Product Family")],
	["valve_type", __("Valve Type")],
	["nominal_size", __("Nominal Size")],
	["pressure_class", __("Pressure Class")],
	["body_material", __("Body Material")],
	["trim_material", __("Trim Material")],
	["end_connection", __("End Connection")],
	["drawing_number", __("Drawing Number")],
	["manufacturer_part_number", __("Manufacturer Part Number")],
	["design_standard", __("Design Standard")],
	["uom", __("UOM")],
	["current_drawing", __("Drawing Revision")],
	["current_product_revision", __("Product Revision")],
	["current_release", __("Engineering Release")],
	["current_bom", __("BOM")],
	["current_routing", __("Routing")],
	["current_inspection_plan", __("Inspection Plan")],
];

const CARRY_FROZEN = {
	Released: true,
	"Released for Production": true,
	Superseded: true,
	Obsolete: true,
	Suspended: true,
	Withdrawn: true,
	Closed: true,
};

function carry_escape(value) {
	return frappe.utils.escape_html(value == null ? "" : String(value));
}

function show_carried_classification(frm, item_field) {
	if (!frm.dashboard || !frm.dashboard.parent) {
		return;
	}
	frm.dashboard.parent.find(".item-classification").remove();
	const item_code = frm.doc[item_field];
	if (!item_code) {
		return;
	}
	frappe
		.call({
			method: "itag_engineering.itag_engineering_management.classification_service.get_item_classification",
			args: { item_code, doctype: frm.doctype, company: frm.doc.company || "" },
		})
		.then((r) => {
			if (!r.message || frm.doc[item_field] !== item_code) {
				return;
			}
			const data = r.message;
			fill_blank_carried_fields(frm, data);
			const cells = CARRY_LABELS.filter((pair) => data[pair[0]])
				.map(
					(pair) =>
						`<div class="col-sm-4" style="margin-bottom: 8px;"><div class="text-muted small">${carry_escape(
							pair[1]
						)}</div><div>${carry_escape(data[pair[0]])}</div></div>`
				)
				.join("");
			if (!cells) {
				return;
			}
			const title = data.item_name
				? __("From Item {0} — {1}", [data.item_code, data.item_name])
				: __("From Item {0}", [data.item_code]);
			frm.dashboard.add_section(
				`<div class="row">${cells}</div>`,
				title,
				"custom item-classification"
			);
		});
}

function carry_document_is_frozen(frm) {
	if ((frm.doc.docstatus || 0) > 0) {
		return true;
	}
	return ["release_status", "revision_status", "workflow_state", "approval_status"].some(
		(field) => frm.fields_dict[field] && CARRY_FROZEN[frm.doc[field]]
	);
}

function fill_blank_carried_fields(frm, data) {
	const values = data.values || {};
	if (carry_document_is_frozen(frm)) {
		return;
	}
	const updates = {};
	Object.keys(values).forEach((field) => {
		if (frm.fields_dict[field] && !frm.doc[field] && values[field]) {
			updates[field] = values[field];
		}
	});
	if (Object.keys(updates).length) {
		frm.set_value(updates);
	}
}

Object.keys(CARRY_ITEM_FIELD).forEach((doctype) => {
	const item_field = CARRY_ITEM_FIELD[doctype];
	const handlers = {
		refresh(frm) {
			show_carried_classification(frm, item_field);
		},
	};
	handlers[item_field] = function (frm) {
		show_carried_classification(frm, item_field);
	};
	frappe.ui.form.on(doctype, handlers);
});

function show_family_products(frm) {
	if (!frm.dashboard || !frm.dashboard.parent) {
		return;
	}
	frm.dashboard.parent.find(".family-products").remove();
	const family = frm.doc.product_family;
	if (!family) {
		frm._family_valve_types = [];
		return;
	}
	frappe
		.call({
			method: "itag_engineering.itag_engineering_management.classification_service.get_family_products",
			args: { product_family: family },
		})
		.then((r) => {
			if (!r.message || frm.doc.product_family !== family) {
				return;
			}
			const products = r.message.products || [];
			const valve_types = r.message.valve_types || [];
			frm._family_valve_types = valve_types.map((row) => row.valve_type);
			if (
				frm.doc.valve_type &&
				frm._family_valve_types.length &&
				!frm._family_valve_types.includes(frm.doc.valve_type)
			) {
				frm.set_value("valve_type", "");
			}
			const family_name = r.message.family_name || family;
			const line = valve_types.length
				? `<div style="display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 12px;">${valve_types
						.map(
							(row) =>
								`<span style="border: 1px solid var(--primary, #2490ef); color: var(--primary, #2490ef); border-radius: 16px; padding: 4px 12px;">${carry_escape(
									row.valve_type_name
								)}</span>`
						)
						.join("")}</div>`
				: `<div class="text-muted" style="margin-bottom: 12px;">${__(
						"No Valve Types are linked to this Product Family yet. Add them on the Product Family."
				  )}</div>`;
			const groups = {};
			products.forEach((row) => {
				const key = row.itag_valve_type || "";
				groups[key] = groups[key] || [];
				groups[key].push(row);
			});
			const ordered = valve_types.map((row) => row.valve_type);
			Object.keys(groups).forEach((key) => {
				if (!ordered.includes(key)) {
					ordered.push(key);
				}
			});
			const tables = ordered
				.map((key) => {
					const rows = groups[key] || [];
					const label =
						(valve_types.find((row) => row.valve_type === key) || {}).valve_type_name ||
						key ||
						__("No Valve Type");
					const body = rows.length
						? rows
								.map(
									(row) => `<tr>
							<td><a href="/app/item/${encodeURIComponent(row.item_code)}">${carry_escape(row.item_code)}</a></td>
							<td>${carry_escape(row.item_name)}</td>
							<td>${carry_escape(row.itag_nominal_size)}</td>
							<td>${carry_escape(row.itag_pressure_class)}</td>
							<td>${carry_escape(row.itag_body_material)}</td>
						</tr>`
								)
								.join("")
						: `<tr><td colspan="5" class="text-muted">${__("No products for this Valve Type yet.")}</td></tr>`;
					return `<div style="margin-bottom: 10px;"><div style="font-weight: 600; margin-bottom: 4px;">${carry_escape(
						label
					)}</div>
						<table class="table table-bordered table-sm"><thead><tr>
							<th>${__("Item Code")}</th><th>${__("Item Name")}</th>
							<th>${__("Nominal Size")}</th><th>${__("Pressure Class")}</th><th>${__("Body Material")}</th>
						</tr></thead><tbody>${body}</tbody></table></div>`;
				})
				.join("");
			frm.dashboard.add_section(
				`${line}${tables || `<div class="text-muted">${__("No products in this family yet.")}</div>`}`,
				__("Products in {0}", [family_name]),
				"custom family-products"
			);
		});
}

function limit_valve_types_to_family(frm) {
	frm.set_query("valve_type", () => {
		const allowed = frm._family_valve_types || [];
		if (!frm.doc.product_family || !allowed.length) {
			return {};
		}
		return { filters: { name: ["in", allowed] } };
	});
}

frappe.ui.form.on("Engineering Item Request", {
	refresh(frm) {
		if (frm.is_new() && !frm.doc.uom) {
			frm.set_value("uom", "Nos");
		}
		limit_valve_types_to_family(frm);
		show_family_products(frm);
	},
	product_family(frm) {
		show_family_products(frm);
	},
});
