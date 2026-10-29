// QA v15.5.12 (c): the request has no Workflow (fix8) and workflow_state is
// hidden, so Frappe's pill fell back to "Submitted". Show the stored state.
// Frappe also loads this file on the form, so list and form pills agree.
frappe.listview_settings["Engineering Item Request"] = {
	add_fields: ["workflow_state", "created_item", "docstatus"],
	get_indicator(doc) {
		if (doc.docstatus === 1 && doc.workflow_state === "Item Created") {
			return [__("Item Created"), "green", "workflow_state,=,Item Created"];
		}
		if (doc.docstatus === 1 && doc.created_item) {
			return [__("Item Created"), "green", "created_item,is,set"];
		}
	},
};
