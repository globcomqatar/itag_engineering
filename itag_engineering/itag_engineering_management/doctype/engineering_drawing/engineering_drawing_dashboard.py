from frappe import _


def get_data():
	"""v15.5.12 #4 (Waheed): Connections tab of Engineering Drawing.
	Engineering Release (drawing_revision) and BOM (itag_drawing_revision)
	link to the drawing; Item, Item Request and ECO are links on the drawing."""
	return {
		"fieldname": "drawing_revision",
		"non_standard_fieldnames": {"BOM": "itag_drawing_revision"},
		"internal_links": {
			"Item": "related_item",
			"Engineering Item Request": "item_request",
			"Engineering Change Order": "applicable_eco",
		},
		"transactions": [
			{"label": _("Item"), "items": ["Item", "Engineering Item Request"]},
			{"label": _("Engineering"), "items": ["BOM", "Engineering Change Order"]},
			{"label": _("Release"), "items": ["Engineering Release"]},
		],
	}
