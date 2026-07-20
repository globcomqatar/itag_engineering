# Training: Engineering Approvers

**Role:** Engineering Approver, Engineering Manager, ITAG Engineering Administrator (the roles that actually release, approve, and drive workflow states forward).

## What you do in this system
You are the release authority: drawings, product revisions, BOMs (via readiness evaluation), Engineering Releases, ECRs, and ECOs all require your approval to progress.

## What you'll actually use
1. **Engineering Drawing / Product Revision** — you release these; the CREATOR cannot (you'll never see this block yourself unless you also happen to be the creator of that specific document — in that case, route it to a colleague).
2. **Engineering Release** — resolve the approval matrix, approve your required discipline's step (segregation of duties: you cannot approve two DIFFERENT disciplines on the same release), then submit once all steps are Approved.
3. **ECR/ECO** — review, request more information, reject (with a real reason), or accept an ECR into a new ECO; approve ECO steps ONLY for disciplines where you actually hold the required role.
4. Review **Segregation of Duties Conflict** and **Permission Exception Report** periodically — these are live checks on the whole approval system's health, not just your own actions.

## What you will NOT be able to do (by design)
- Approve two different approval-matrix disciplines on the same Engineering Release/ECO as the same person.
- Release a drawing you personally created (Administrator is the only exception, for break-glass purposes only).

## Where to check status
**Release Approval Aging**, **ECO Approval Aging**, **ECR Aging and Status**, **Engineering Release Register**.
