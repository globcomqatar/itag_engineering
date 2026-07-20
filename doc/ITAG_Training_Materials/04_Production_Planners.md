# Training: Production Planners

**Role:** Production Planner.

## What you do in this system
You plan Work Orders against the currently-effective Engineering Release baseline and monitor production continuation/rework needs.

## What you'll actually use
1. Confirm **Effective Release by Item** before planning a Work Order — a Work Order cannot be submitted without a currently-effective Engineering Release for that Item/Company (`freeze_baseline_before_submit()` blocks it).
2. You may submit an Engineering Change Request when a change is needed (you're in `ecr_service.SUBMIT_ROLES`) — but you cannot accept it into an ECO or approve it.
3. **Production Continuation Register** and **Remaining Quantity Exceptions** — monitor stopped/continued Work Orders and any quantity reconciliation problems.
4. **Missing Engineering Baseline** / **Open Work Orders Without Frozen Baseline** — these should normally be EMPTY; a non-empty result means a legacy or bypassed Work Order needs investigation, not routine planning action.

## What you will NOT be able to do (by design)
- Submit a Work Order against an Item/Company with no effective Engineering Release.
- Approve or accept your own Engineering Change Request.

## Where to check status
**Engineering Release Register**, **Work Orders by Engineering Baseline**, **Production Continuation Register**.
