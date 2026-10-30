"""v15.5.14 build 2 (Waheed via Ahmed, 30-Oct-2026): copy every Item's
custom_product_type into itag_engineering's own itag_item_type, with General
-> Non-Product. custom_product_type and erpcloud_itagksa are untouched;
nothing is deleted. Rollback: clear itag_item_type (old field is intact)."""

from itag_engineering.itag_engineering_management.item_type_options import copy_product_type_to_itag_item_type
from itag_engineering.setup.custom_fields import sync_custom_fields


def execute():
	sync_custom_fields()  # post_model_sync runs before after_migrate
	changed = copy_product_type_to_itag_item_type()
	print(f"v15.5.14 Item Type copied to itag_item_type: {len(changed)} Item(s)")
