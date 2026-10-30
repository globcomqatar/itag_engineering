from frappe import _


def get_data():
	"""fix9: Connections tab. Product Revision and Engineering Release are
	matched on item = created_item (see item_request_links.get_open_count and
	the form script)."""
	return {
		"fieldname": "item_request",
		"non_standard_fieldnames": {
			"BOM": "itag_item_request",
			"Product Revision": "item",
			"Engineering Release": "item",
		},
		"internal_links": {"Item": "created_item"},
		"transactions": [
			{"label": _("Item"), "items": ["Item"]},
			{"label": _("Engineering"), "items": ["Engineering Drawing", "BOM"]},
			{"label": _("Revision and Release"), "items": ["Product Revision", "Engineering Release"]},
		],
	}
