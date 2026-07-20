# ITAG Engineering Management — UAT Sign-off Cross-Reference

**Build:** ITAG-1.0.0 (Production Release and Certification), Task 2
**Roadmap reference:** Section 24.4 — all 20 UAT scenarios (UAT-001 through UAT-020) must PASS or have a formally approved exception.

## Appendix B (UAT Ownership Matrix) — not found

This task's plan calls for consulting a bench-level "Appendix B UAT Ownership Matrix" to assign each UAT scenario's real business owner, rather than inventing names. A repository-wide search found **no such document anywhere in this program** — no master roadmap file, no `ITAG_Decisions.md`, no Appendix B of any kind exists in this repository. This is consistent with Build ITAG-0.9.0's own finding that `doc/ITAG_Decisions.md` does not exist in this repository either.

**Business-owner names below are therefore left as open placeholders (role titles only, e.g. "Engineering Manager"), not invented individuals.** The actual named approvers must fill these in — do not treat the role title as a substitute for a real named sign-off.

## Cross-reference table

Every UAT number has at least one automated regression test class, re-collected in full by Build ITAG-0.11.0's `itag_engineering/tests/test_full_uat_regression.py`. Several numbers have more than one distinct scenario class (built across different phases as the roadmap's own scenario coverage grew) — every one is listed, not just a representative.

| UAT # | Scenario | Owning Build | Test File | Test Class | Automated Evidence | Business Owner (role) | Real Sign-off |
|---|---|---|---|---|---|---|---|
| UAT-001 | New Manufactured Valve Item | ITAG-0.2.0 | `tests/test_uat_001_002.py` | `TestUAT001NewManufacturedValveItem` | Present | Engineering Manager | ☐ Pending |
| UAT-002 | Duplicate Item Prevention | ITAG-0.2.0 | `tests/test_uat_001_002.py` | `TestUAT002DuplicateItemPrevention` | Present | Engineering Manager | ☐ Pending |
| UAT-003 | Initial Product Release | ITAG-0.5.0 | `tests/test_uat_003_004_014_018.py` | `TestUAT003InitialProductRelease` | Present | Engineering Approver | ☐ Pending |
| UAT-003 | Multi-Level BOM Preparation | ITAG-0.4.0 | `tests/test_uat_003_005_011.py` | `TestUAT003MultiLevelBOMPreparation` | Present | Engineering Manager | ☐ Pending |
| UAT-003 | Product Revision Creation | ITAG-0.3.0 | `tests/test_uat_018_003.py` | `TestUAT003ProductRevisionCreation` | Present | Engineering Manager | ☐ Pending |
| UAT-004 | Work Order Baseline Freeze | ITAG-0.5.0 | `tests/test_uat_003_004_014_018.py` | `TestUAT004WorkOrderBaselineFreeze` | Present | Production Manager | ☐ Pending |
| UAT-005 | ECR to ECO Creation | ITAG-0.6.0 | `tests/test_uat_005_017.py` | `TestUAT005ECRToECOCreation` | Present | Engineering Manager | ☐ Pending |
| UAT-005 | Multi-Level BOM Revision Comparison | ITAG-0.4.0 | `tests/test_uat_003_005_011.py` | `TestUAT005MultiLevelBOMRevisionComparison` | Present | Engineering Manager | ☐ Pending |
| UAT-005 | Multi-Level BOM Revision Impact | ITAG-0.7.0 | `tests/test_uat_005_019.py` | `TestUAT005MultiLevelBOMRevisionImpact` | Present | Engineering Manager | ☐ Pending |
| UAT-006 | Continue Under Old Revision | ITAG-0.8.0 | `tests/test_uat_006_010_012_013.py` | `TestUAT006ContinueUnderOldRevision` | Present | Production Manager | ☐ Pending |
| UAT-007 | Stop and Continue | ITAG-0.9.0 | `tests/test_uat_007_008_009_020.py` | `TestUAT007StopAndContinue` | Present | Production Supervisor | ☐ Pending |
| UAT-008 | Existing Component Reuse | ITAG-0.9.0 | `tests/test_uat_007_008_009_020.py` | `TestUAT008ExistingComponentReuse` | Present | Production Supervisor | ☐ Pending |
| UAT-009 | Rework Existing WIP | ITAG-0.9.0 | `tests/test_uat_007_008_009_020.py` | `TestUAT009ReworkExistingWIP` | Present | Quality Manager | ☐ Pending |
| UAT-010 | Scrap Incompatible Material | ITAG-0.8.0 | `tests/test_uat_006_010_012_013.py` | `TestUAT010ScrapIncompatibleMaterial` | Present | Quality Manager | ☐ Pending |
| UAT-011 | Hold-Point Inspection Preparation | ITAG-0.4.0 | `tests/test_uat_003_005_011.py` | `TestUAT011HoldPointInspectionPreparation` | Present | Quality Manager | ☐ Pending |
| UAT-011 | Hold-Point Inspection Completion | ITAG-0.10.0 | `tests/test_uat_011_015_016.py` | `TestUAT011HoldPointInspectionCompletion` | Present | Quality Manager | ☐ Pending |
| UAT-012 | Engineering Hold | ITAG-0.8.0 | `tests/test_uat_006_010_012_013.py` | `TestUAT012EngineeringHold` | Present | Quality Manager | ☐ Pending |
| UAT-013 | Deviation Quantity and Expiry | ITAG-0.8.0 | `tests/test_uat_006_010_012_013.py` | `TestUAT013DeviationQuantityAndExpiry` | Present | Quality Manager | ☐ Pending |
| UAT-014 | Customer-Specific Release | ITAG-0.5.0 | `tests/test_uat_003_004_014_018.py` | `TestUAT014CustomerSpecificRelease` | Present | Sales User / Engineering Approver | ☐ Pending |
| UAT-015 | Full Finished-Valve Traceability | ITAG-0.10.0 | `tests/test_uat_011_015_016.py` | `TestUAT015FullFinishedValveTraceability` | Present | Quality Manager | ☐ Pending |
| UAT-016 | Forward Heat Traceability | ITAG-0.10.0 | `tests/test_uat_011_015_016.py` | `TestUAT016ForwardHeatTraceability` | Present | Quality Manager | ☐ Pending |
| UAT-017 | Unauthorized Approval | ITAG-0.6.0 | `tests/test_uat_005_017.py` | `TestUAT017UnauthorizedApproval` | Present | ITAG Engineering Administrator | ☐ Pending |
| UAT-018 | Released Drawing Immutability | ITAG-0.3.0 | `tests/test_uat_018_003.py` | `TestUAT018ReleasedDrawingImmutability` | Present | Engineering Manager | ☐ Pending |
| UAT-018 | Released Drawing Immutability Regression | ITAG-0.5.0 | `tests/test_uat_003_004_014_018.py` | `TestUAT018ReleasedDrawingImmutabilityRegression` | Present | Engineering Manager | ☐ Pending |
| UAT-019 | ECO Analysis Staleness | ITAG-0.7.0 | `tests/test_uat_005_019.py` | `TestUAT019ECOAnalysisStaleness` | Present | Engineering Manager | ☐ Pending |
| UAT-020 | Idempotent Successor Creation | ITAG-0.9.0 | `tests/test_uat_007_008_009_020.py` | `TestUAT020IdempotentSuccessorCreation` | Present | Production Manager | ☐ Pending |

**Consolidation point:** all 26 rows above (UAT-001 through UAT-020, several numbers appearing more than once) are re-collected and re-run from a single module, `itag_engineering/tests/test_full_uat_regression.py` (Build ITAG-0.11.0 Task 7), by importing each class under its original name.

## What "Automated Evidence: Present" means, and does not mean

"Present" means the test class exists, is syntactically valid, and was confirmed importable by this session's `python3 -m py_compile` sweep (see `ITAG_Final_Regression_Evidence.md`). **It does NOT mean these tests were actually executed and observed to pass against a live site in this session** — there is no bench in this environment to run them on. Before any UAT scenario is marked genuinely passed for certification purposes, `bench run-tests --app itag_engineering --module itag_engineering.tests.test_full_uat_regression` (or the equivalent full-suite invocation) must be run for real, and its actual pass/fail output attached to this document.

## Real human sign-off — required, not simulated

**Every "Real Sign-off" cell above is intentionally left as `☐ Pending`.** Per this task's own plan: *"Present the sign-off document to the user for review — this requires actual human business-owner approval, which an agent cannot substitute for."* This document is the artifact those human owners review and initial/sign against — it is not itself a sign-off. Do not treat any row as approved until a named human with actual authority for that scenario has reviewed the real test execution (not this cross-reference) and confirmed acceptance, and do not carry this build to certification (`ITAG_Production_Certification.md`) while any row remains `☐ Pending` without an explicitly recorded, approved exception.
