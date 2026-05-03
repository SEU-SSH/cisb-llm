/**
 * @name Compiler-Introduced Security Bug: Memory Read Reordering
 * @description Detects cases where a synchronization flag in shared memory is read after dependent data,
 *              lacking explicit ordering constraints, potentially causing stale data processing due to compiler optimization.
 * @kind problem
 * @problem.severity warning
 * @precision high
 * @tags security, cisb, memory-reordering
 */

import cpp
import CISB_MemoryReorder

from RootCauseUnit base, DataFlow::Node dataRead, DataFlow::Node syncRead
where base.hasDependentDataRead(dataRead) and
      base.hasSyncFlagRead(syncRead) and
      controlFlowUnit(dataRead, syncRead) and
      environmentUnit(base, dataRead, syncRead)
select dataRead, "Compiler may reorder reads: dependent data accessed before synchronization flag in shared memory without barriers."
