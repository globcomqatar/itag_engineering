"""fix9 (Waheed, 29-Oct-2026): adds BOM.itag_item_request (Link to
Engineering Item Request). Engineering Drawing.item_request comes from the
DocType JSON sync. Additive and idempotent; no record is changed or deleted.
Rollback: redeploy 15.5.9; the field can be hidden, data stays."""

from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

from itag_engineering.setup.custom_fields import get_item_request_link_fields


def execute():
	create_custom_fields(get_item_request_link_fields(), update=True)
