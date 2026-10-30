# Item codes with Document Naming Rule (v15.5.14)

Standard Frappe feature, set up on each site in the Desk. Nothing here is shipped as a fixture.

## How it works
- An Engineering Item Request submit builds the Item and inserts it **without** a fixed name.
- Frappe runs `Document Naming Rule` before ERPNext's `Item.autoname` (see `frappe/model/naming.py` `set_new_name`), so Stock Settings "Item Naming By" / naming series never applies to these Items.
- `itag_engineering` hook `Item.before_validate` (`item_naming.sync_item_code_with_naming_rule`) copies the generated name into `item_code` on insert.
- The Item keeps `itag_engineering_item_request` (back-link to the request). After insert the code checks name == item_code; on a mismatch the submit rolls back.
- If **no** Document Naming Rule matches, the request falls back to the old Item Code Rule on the Valve Type (reserved with `set_name`, so the naming series cannot override it either).

## Sample setup (Desk > Document Naming Rule > New)
| Field | Value |
|---|---|
| Document Type | Item |
| Priority | 10 (higher wins) |
| Prefix | `BV-` or `{itag_nominal_size}-BV-` (prefix may read Item fields with `{fieldname}`) |
| Digits | 5 |
| Conditions | `itag_valve_type` `=` `Ball Valve` |

Result: `BV-00001`, `BV-00002`, ...

## Limits
- One counter per rule: with a field in the prefix (e.g. size), the number still runs across all sizes.
- One rule per valve type (or per condition set). A new valve type needs a new rule.
- Conditions see only fields set on the Item at insert (the request maps product family, valve type, sizes, materials, drawing number, Item Group, Item Type).

## Item Code Rule
The Item Code Rule doctype and its data are kept. It is no longer used when a Document Naming Rule matches; it is only the fallback for Valve Types without one.
