# Training: Workshop Technicians

**Role:** Workshop Technician.

## What you do in this system
You physically execute operations on the shop floor: starting/completing Job Card operations, working hold-point inspections, and executing rework instructions.

## What you'll actually use
1. **Job Card** — start and complete operations against your assigned Work Order. If it's blocked, the system tells you exactly which Production Engineering Hold is stopping you and why — do not attempt to work around a hold; escalate to your supervisor.
2. **Hold-point / witness-point operations** — a BOM operation row flagged as a hold or witness point requires a real Inspection Requirement to be satisfied before the job can proceed past that point.
3. **Rework Instruction** — you'll complete `required_operations`/`inspection_steps` rows one at a time; the instruction cannot close until every row is marked complete/passed — mark each one honestly as you actually finish it, not in advance.

## What you will NOT be able to do (by design)
- Approve or release any engineering document (drawings, releases, ECOs).
- Place or release a Production Engineering Hold yourself.
- Complete a rework instruction with operations/inspections still outstanding.

## Where to check status
**Operation Hold Point Register**, **Rework Instruction Status**.
