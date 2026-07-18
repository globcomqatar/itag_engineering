// Copyright (c) 2026, Globcom Qatar and contributors
// For license information, please see license.txt

frappe.ui.form.on("Engineering Settings", {
	refresh(frm) {
		// The server method enforces its own role gate (System Manager /
		// ITAG Engineering Administrator); this button is only a convenience.
		frm.add_custom_button(__("Validate Configuration"), () => {
			frm.call("validate_configuration").then((r) => {
				if (!r.message) {
					return;
				}
				const result = r.message;
				const status_color = { pass: "green", fail: "red", info: "blue" };
				const rows = (result.checks || [])
					.map(
						(c) => `
						<tr>
							<td>${frappe.utils.escape_html(c.check || "")}</td>
							<td><span class="indicator-pill ${status_color[c.status] || "gray"}">
								${frappe.utils.escape_html(c.status)}</span></td>
							<td>${frappe.utils.escape_html(c.message || "")}</td>
						</tr>`
					)
					.join("");
				frappe.msgprint({
					title: __("Configuration Readiness: {0}", [result.readiness_status]),
					indicator: result.ready ? "green" : "orange",
					wide: true,
					message: `
						<table class="table table-bordered">
							<thead>
								<tr>
									<th>${__("Check")}</th>
									<th>${__("Status")}</th>
									<th>${__("Message")}</th>
								</tr>
							</thead>
							<tbody>${rows}</tbody>
						</table>`,
				});
				frm.reload_doc();
			});
		});
	},
});
