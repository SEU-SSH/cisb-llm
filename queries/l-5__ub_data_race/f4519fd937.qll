import cpp

/**
 * Root Cause Unit: Identifies reads of a synchronization flag and dependent data 
 * originating from the same shared memory base object.
 */
class RootCauseUnit extends DataFlow::Node {
  RootCauseUnit() { this.asExpr().getType().isPointerOrReferenceType() }
  
  predicate hasSyncFlagRead(DataFlow::Node syncRead) {
    syncRead instanceof ReadExpr and
    syncRead.asExpr().getType().isBooleanType() and
    DataFlow::exprHasSource(syncRead, this)
  }
  
  predicate hasDependentDataRead(DataFlow::Node dataRead) {
    dataRead instanceof ReadExpr and
    not dataRead.asExpr().getType().isBooleanType() and
    DataFlow::exprHasSource(dataRead, this)
  }
}

/**
 * Control Flow Unit: Ensures the dependent data is read before the sync flag 
 * within the same function, without intervening memory barriers.
 */
predicate controlFlowUnit(DataFlow::Node dataRead, DataFlow::Node syncRead) {
  dataRead.asExpr().getEnclosingFunction() = syncRead.asExpr().getEnclosingFunction() and
  dataRead.asExpr().getStmt().getSourceLocation().compareTo(syncRead.asExpr().getStmt().getSourceLocation()) < 0 and
  not exists(MemoryBarrierCall barrier |
    barrier.getEnclosingFunction() = dataRead.asExpr().getEnclosingFunction() and
    barrier.getStmt().getSourceLocation().compareTo(dataRead.asExpr().getStmt().getSourceLocation()) > 0 and
    barrier.getStmt().getSourceLocation().compareTo(syncRead.asExpr().getStmt().getSourceLocation()) < 0
  )
}

/**
 * Environment Unit: Captures assumptions about shared memory access and 
 * the absence of explicit ordering constraints (volatile/barriers).
 */
predicate environmentUnit(DataFlow::Node baseNode, DataFlow::Node dataRead, DataFlow::Node syncRead) {
  baseNode.asExpr().getType().hasQualifier("volatile") = false and
  not exists(AccessMacro macro |
    macro.getEnclosingFunction() = baseNode.asExpr().getEnclosingFunction() and
    macro.getStmt().getSourceLocation().compareTo(dataRead.asExpr().getStmt().getSourceLocation()) > 0 and
    macro.getStmt().getSourceLocation().compareTo(syncRead.asExpr().getStmt().getSourceLocation()) < 0
  )
}

/** Helper class for memory barrier calls */
class MemoryBarrierCall extends CallExpression {
  MemoryBarrierCall() {
    this.getCalleeName().regexpMatch("(rmb|wmb|mb|read_barrier_depends|smp_rmb|smp_mb)")
  }
}

/** Helper class for explicit access macros */
class AccessMacro extends MacroInvocation {
  AccessMacro() { this.getName().regexpMatch("(READ_ONCE|ACCESS_ONCE|VolatileRead)") }
}
