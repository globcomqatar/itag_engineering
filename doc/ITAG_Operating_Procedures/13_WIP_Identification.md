# Operating Procedure: WIP Identification

**Roadmap:** Section 24.5 item 13 / Section 21. **Build:** ITAG-0.10.0.

## What's actually built
- Policy: reuses ITAG-0.2.0's `Item.itag_wip_unit_tracking_required` (and `itag_serial_tracking_required`/`itag_batch_tracking_required`/`itag_heat_tracking_required`) — no separate new policy DocType.
- DocType: `WIP Unit Register` — created from a Job Card via `wip_service.should_create_wip_unit()`/`create_wip_unit_from_job_card()` (idempotent per Work Order — multiple Job Cards for the same Work Order all progress the SAME WIP Unit, never one each). Copies `drawing_revision`/`bom_revision`/`product_revision`/`engineering_release` from the originating Work Order's frozen baseline at creation. `quality_status`/`hold_status`/`rework_status`/`disposition_status` are read-only, kept live by `wip_service.refresh_wip_status()` — never hand-edited.
- Child table: `WIP Component Link` — records genealogy (which components were consumed into which assembly). `wip_service.link_component_to_assembly()` blocks creating a link that would form a genealogy CYCLE, checked before the link is created, and is itself permission-gated (`WIP_ACTION_ROLES`).
- Reports: **WIP Unit Status**, **WIP Aging**, **Work Orders by Engineering Revision**, **Job Cards by Drawing Revision**.

## Procedure
1. For any Item with `itag_wip_unit_tracking_required` set, a WIP Unit Register entry is created automatically the first time a Job Card against its Work Order reaches a tracked operation stage — no manual creation is normally needed.
2. When a component is consumed into an assembly, call **Link Component to Assembly** with the parent and component WIP Unit names and quantity consumed — the system rejects any link that would make a unit its own (direct or indirect) ancestor.
3. Status fields (`quality_status`, `hold_status`, `rework_status`, `disposition_status`) always reflect the REAL current state of the linked Quality Inspection/Hold/Rework Instruction/Material Disposition records — if a status looks stale, call **Refresh WIP Status** rather than editing the field directly (it's read-only and will reject a manual edit).
4. Use **WIP Unit Status** / **WIP Aging** to monitor units in process.

## Escalation
A rejected component link ("would create a genealogy cycle") means the proposed parent is already, transitively, a component of the unit you're trying to consume — verify the actual physical assembly structure before overriding anything.
