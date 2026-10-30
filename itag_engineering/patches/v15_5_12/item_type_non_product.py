"""v15.5.12 #3 (Waheed): Engineering Item Request Item Type "General" ->
"Non-Product" in place, and Item.custom_product_type gains Critical /
Non-Critical / Non-Product (General kept). Idempotent; nothing deleted.
Rollback: redeploy 15.5.11 and set item_type back from the patch log."""

import frappe

from itag_engineering.itag_engineering_management.item_type_options import (
	ensure_item_product_type_options,
	rename_general_to_non_product,
)


def execute():
	renamed = rename_general_to_non_product()
	if renamed:
		print("v15.5.12 item_type General -> Non-Product:", ", ".join(renamed))
	ensure_item_product_type_options()
