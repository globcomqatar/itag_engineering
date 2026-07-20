# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

"""Full UAT-001 through UAT-020 regression rerun (roadmap Section 22.11 /
Build ITAG-0.11.0 Task 7).

Re-exports every TestUAT* class built across Builds ITAG-0.2.0 through
0.10.0 into this single module, by its ORIGINAL name (`import ... as
<same name>`) - not a restatement of their logic, but the same test
classes, genuinely re-collected and re-run from here against this build's
final state. A test runner that discovers tests by module (unittest
discover, pytest, `bench run-tests`) picks up and executes each one again
when it scans this file, exactly as roadmap Section 22.11 requires
("All UAT scenarios UAT-001 through UAT-020 shall be rerun at least once
against the release-candidate data set").

Two or more classes cover the same UAT number from different builds/
angles (e.g. UAT-003 has 4 distinct scenario classes, UAT-005 has 3,
UAT-011 and UAT-018 each have 2) - every one of them is re-collected
here, not just one representative per number, since the roadmap's own UAT
scenarios were written to be re-run in full, not sampled.
"""

from itag_engineering.tests.test_uat_001_002 import (
	TestUAT001NewManufacturedValveItem as TestUAT001NewManufacturedValveItem,
)
from itag_engineering.tests.test_uat_001_002 import (
	TestUAT002DuplicateItemPrevention as TestUAT002DuplicateItemPrevention,
)
from itag_engineering.tests.test_uat_003_004_014_018 import (
	TestUAT003InitialProductRelease as TestUAT003InitialProductRelease,
)
from itag_engineering.tests.test_uat_003_004_014_018 import (
	TestUAT004WorkOrderBaselineFreeze as TestUAT004WorkOrderBaselineFreeze,
)
from itag_engineering.tests.test_uat_003_004_014_018 import (
	TestUAT014CustomerSpecificRelease as TestUAT014CustomerSpecificRelease,
)
from itag_engineering.tests.test_uat_003_004_014_018 import (
	TestUAT018ReleasedDrawingImmutabilityRegression as TestUAT018ReleasedDrawingImmutabilityRegression,
)
from itag_engineering.tests.test_uat_003_005_011 import (
	TestUAT003MultiLevelBOMPreparation as TestUAT003MultiLevelBOMPreparation,
)
from itag_engineering.tests.test_uat_003_005_011 import (
	TestUAT005MultiLevelBOMRevisionComparison as TestUAT005MultiLevelBOMRevisionComparison,
)
from itag_engineering.tests.test_uat_003_005_011 import (
	TestUAT011HoldPointInspectionPreparation as TestUAT011HoldPointInspectionPreparation,
)
from itag_engineering.tests.test_uat_005_017 import (
	TestUAT005ECRToECOCreation as TestUAT005ECRToECOCreation,
)
from itag_engineering.tests.test_uat_005_017 import (
	TestUAT017UnauthorizedApproval as TestUAT017UnauthorizedApproval,
)
from itag_engineering.tests.test_uat_005_019 import (
	TestUAT005MultiLevelBOMRevisionImpact as TestUAT005MultiLevelBOMRevisionImpact,
)
from itag_engineering.tests.test_uat_005_019 import (
	TestUAT019ECOAnalysisStaleness as TestUAT019ECOAnalysisStaleness,
)
from itag_engineering.tests.test_uat_006_010_012_013 import (
	TestUAT006ContinueUnderOldRevision as TestUAT006ContinueUnderOldRevision,
)
from itag_engineering.tests.test_uat_006_010_012_013 import (
	TestUAT010ScrapIncompatibleMaterial as TestUAT010ScrapIncompatibleMaterial,
)
from itag_engineering.tests.test_uat_006_010_012_013 import (
	TestUAT012EngineeringHold as TestUAT012EngineeringHold,
)
from itag_engineering.tests.test_uat_006_010_012_013 import (
	TestUAT013DeviationQuantityAndExpiry as TestUAT013DeviationQuantityAndExpiry,
)
from itag_engineering.tests.test_uat_007_008_009_020 import (
	TestUAT007StopAndContinue as TestUAT007StopAndContinue,
)
from itag_engineering.tests.test_uat_007_008_009_020 import (
	TestUAT008ExistingComponentReuse as TestUAT008ExistingComponentReuse,
)
from itag_engineering.tests.test_uat_007_008_009_020 import (
	TestUAT009ReworkExistingWIP as TestUAT009ReworkExistingWIP,
)
from itag_engineering.tests.test_uat_007_008_009_020 import (
	TestUAT020IdempotentSuccessorCreation as TestUAT020IdempotentSuccessorCreation,
)
from itag_engineering.tests.test_uat_011_015_016 import (
	TestUAT011HoldPointInspectionCompletion as TestUAT011HoldPointInspectionCompletion,
)
from itag_engineering.tests.test_uat_011_015_016 import (
	TestUAT015FullFinishedValveTraceability as TestUAT015FullFinishedValveTraceability,
)
from itag_engineering.tests.test_uat_011_015_016 import (
	TestUAT016ForwardHeatTraceability as TestUAT016ForwardHeatTraceability,
)
from itag_engineering.tests.test_uat_018_003 import (
	TestUAT003ProductRevisionCreation as TestUAT003ProductRevisionCreation,
)
from itag_engineering.tests.test_uat_018_003 import (
	TestUAT018ReleasedDrawingImmutability as TestUAT018ReleasedDrawingImmutability,
)

# UAT-001 through UAT-020, confirmed present at least once (several numbers
# have more than one scenario class - see this module's own docstring).
COVERED_UAT_NUMBERS = tuple(range(1, 21))
