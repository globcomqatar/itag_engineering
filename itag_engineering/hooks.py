app_name = "itag_engineering"
app_title = "ITAG Engineering Management"
app_publisher = "Globcom Qatar"
app_description = "Engineering Management and Product Lifecycle control layer for ERPNext Manufacturing (valve manufacturing)"
app_email = "waheed@globcomqatar.com"
app_license = "mit"

required_apps = ["erpnext"]

# Installation
# ------------

after_install = "itag_engineering.install.after_install"

# Migration
# ---------

after_migrate = "itag_engineering.setup.custom_fields.sync_custom_fields"

# Testing
# -------

before_tests = "itag_engineering.install.before_tests"
