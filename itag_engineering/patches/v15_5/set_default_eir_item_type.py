# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

"""Give every Engineering Item Request an Item Type.

Item Type on the request is now mandatory because it feeds the Item's
custom_product_type, which erpcloud_itagksa makes mandatory. Requests saved
before that have a blank value. They get General, the field's default, so they
can still be approved and turned into Items. Requests that already have a value
are not touched, so the patch is safe to run again.
"""

import frappe

from itag_engineering.itag_engineering_management.classification_service import DEFAULT_PRODUCT_TYPE


def execute():
	if not frappe.db.table_exists("Engineering Item Request"):
		return
	if not frappe.db.has_column("Engineering Item Request", "item_type"):
		return
	frappe.db.sql(
		"""
		update `tabEngineering Item Request`
		set item_type = %s
		where ifnull(item_type, '') = ''
		""",
		(DEFAULT_PRODUCT_TYPE,),
	)
