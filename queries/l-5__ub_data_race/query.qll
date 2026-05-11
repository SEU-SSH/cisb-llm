import cpp
import semmle.code.cpp.dataflow.DataFlow

/**
 * Root Cause Unit: Identifies reads of a synchronization flag and dependent data
 * originating from the same shared memory base object.
 */
class RootCauseUnit extends DataFlow::Node {
  RootCauseUnit() {
    exists(Expr e |
      e = this.asExpr() and
      (e.getType() instanceof PointerType or e.getType() instanceof ReferenceType)
    )
  }

  predicate hasSyncFlagRead(DataFlow::Node syncRead) {
    exists(Expr e |
      e = syncRead.asExpr() and
      e.getType().getName() = "bool"
    ) and
    DataFlow::localFlow(this, syncRead)
  }

  predicate hasDependentDataRead(DataFlow::Node dataRead) {
    exists(Expr e |
      e = dataRead.asExpr() and
      e.getType().getName() != "bool"
    ) and
    DataFlow::localFlow(this, dataRead)
  }
}

/**
 * Control Flow Unit: Ensures the dependent data is read before the sync flag
 * within the same function, without intervening memory barriers.
 */
predicate controlFlowUnit(DataFlow::Node dataRead, DataFlow::Node syncRead) {
  dataRead.asExpr().getEnclosingFunction() = syncRead.asExpr().getEnclosingFunction() and
  dataRead.asExpr().getLocation().getStartLine() < syncRead.asExpr().getLocation().getStartLine() and
  not exists(MemoryBarrierCall barrier |
    barrier.getEnclosingFunction() = dataRead.asExpr().getEnclosingFunction() and
    barrier.getLocation().getStartLine() > dataRead.asExpr().getLocation().getStartLine() and
    barrier.getLocation().getStartLine() < syncRead.asExpr().getLocation().getStartLine()
  )
}

/**
 * Environment Unit: Captures assumptions about shared memory access and
 * the absence of explicit ordering constraints (volatile/barriers).
 */
predicate environmentUnit(DataFlow::Node baseNode, DataFlow::Node dataRead, DataFlow::Node syncRead) {
  not baseNode.asExpr().getType().isVolatile() and
  not exists(AccessMacro macro |
    macro.getLocation().getStartLine() > dataRead.asExpr().getLocation().getStartLine() and
    macro.getLocation().getStartLine() < syncRead.asExpr().getLocation().getStartLine()
  )
}

/** Helper class for memory barrier calls */
class MemoryBarrierCall extends FunctionCall {
  MemoryBarrierCall() {
    this.getTarget().getName().regexpMatch("(rmb|wmb|mb|read_barrier_depends|smp_rmb|smp_mb)")
  }
}

/** Helper class for explicit access macros */
class AccessMacro extends MacroInvocation {
  AccessMacro() { this.getMacroName().regexpMatch("(READ_ONCE|ACCESS_ONCE|VolatileRead)") }
}
