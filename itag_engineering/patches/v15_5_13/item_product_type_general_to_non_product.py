"""v15.5.13 #7 (Waheed): Items still on Item Type (custom_product_type)
General -> Non-Product in place. Staging had none on 29-Oct-2026; this is a
safety net. Idempotent; nothing deleted; changed Items are printed to the
migrate log. Rollback: set the printed Items back to General."""

from itag_engineering.itag_engineering_management.item_type_options import items_general_to_non_product


def execute():
	changed = items_general_to_non_product()
	print(
		"v15.5.13 Item custom_product_type General -> Non-Product: "
		+ (", ".join(changed) if changed else "none")
	)
