# Operating Procedure: Drawing Revision

**Roadmap:** Section 24.5 item 2. **Build:** ITAG-0.3.0 (immutability), ITAG-0.11.0 Task 1 (creator/releaser segregation).

## What's actually built
- DocType: `Engineering Drawing` — `release_status` mirrors `workflow_state` (kept in sync by `sync_release_status_from_workflow_state()`); a released drawing (`Released`/`Superseded`/`Obsolete`) is immutable except for a small allowed-field set (`validate_immutable_once_released()`).
- Service: `drawing_service.py` — `create_new_drawing_revision(drawing_number, new_revision, **fields)` can only start from an already-`Released` source revision; carries forward `related_item`/`product_family`/`applicable_standard`/`security_classification`.
- Checksum: `checksum_service.sync_drawing_checksum()` computes `file_checksum` from the attached file automatically; a drawing cannot reach `Released` without one (`validate_release_requires_checksum()`), and the approved file cannot be swapped afterward.
- Segregation of duties (ITAG-0.11.0): the same user who created a drawing may not also be the one whose save transitions it to `Released` (`validate_creator_cannot_release()`) — a different Engineering Approver must perform the release. Administrator is exempt (break-glass account).
- Reports: **Drawing Revision Register**, **Drawing Approval Aging**, **Missing Released Drawing File**.

## Procedure
1. Create a new `Engineering Drawing` (first revision) or call **Create New Drawing Revision** against an already-Released source — attach the drawing file.
2. Submit through the workflow to Approved. The checksum populates automatically from the attached file when it's set.
3. A **different** Engineering Approver (not the creator) performs the Release transition. If the same user who created it attempts to release it, the system blocks the save with an explicit error — route to another approver instead.
4. Once Released, the file and revision data are frozen — a further revision must go through step 1 again as a NEW `Engineering Drawing` record, never an edit to this one.
5. Verify: **Drawing Revision Register** shows the new revision with a non-blank checksum.

## Escalation
If a legitimate correction is needed to an already-Released drawing, do not attempt to bypass immutability — create a new revision through the normal path.
