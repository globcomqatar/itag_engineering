# Operating Procedure: Engineering Hold

**Roadmap:** Section 24.5 item 8 / Section 18.4. **Build:** ITAG-0.8.0.

## What's actually built
- DocType: `Production Engineering Hold` — `reference_doctype` scopes to Item, Batch, Serial No, Work Order, Job Card, Product Revision, Engineering Release, WIP Unit Register (ITAG-0.10.0), Warehouse, Purchase Receipt, Delivery Note, or Project, with a `Hold Blocked Action` child table naming exactly which actions are blocked.
- Service: `hold_service.py` — `place_hold(**fields)` (Engineering Manager/ITAG Engineering Administrator/Quality Manager) defaults to blocking all 9 holdable actions unless specific ones are named; `release_hold(hold_name, release_reason)` requires a real reason. `is_reference_held()` checks not just the exact reference but every transitive scope (a Work Order is also held if its Item, Product Revision, or Engineering Release is held; a Job Card is held if its Work Order is held). Both log "Hold Placement"/"Hold Release" (ITAG-0.11.0).
- Enforcement: wired via `doc_events` on Job Card (start, complete operation), Stock Entry (transfer/consume), Quality Inspection (submit), Delivery Note (deliver) — blocks the action outright with the hold's own reason shown to the user.
- Reports: **Active Production Holds**, **Hold Aging**, **Material Under Engineering Hold**, **Components Under Engineering Hold**, **Quarantined Engineering Stock**, **Operation Hold Point Register**.

## Procedure
1. To place a hold, identify the correct scope (Item/Batch/Serial/Work Order/Product Revision/Release/WIP Unit) and call **Place Hold** with a clear `hold_reason`. By default this blocks every listed action against that reference and everything transitively tied to it.
2. Confirm the hold is visible in **Active Production Holds** and that the specific blocked action is actually rejected when attempted (e.g. try starting a Job Card on a held Work Order — it must be refused with the hold's reason shown).
3. To release, call **Release Hold** with a real, specific release reason — a blank reason is rejected.
4. If only a NARROW unblock is needed (e.g. UAT-006's "Continue Under Old Revision" disposition), do not release the whole hold — use the Material Disposition's own narrow unblock instead (see Material Disposition procedure).

## Escalation
If a hold appears not to be blocking an action you expect it to, check whether the reference scope is transitive (Item-level holds cascade to every Work Order building that Item) before assuming the hold is broken.
