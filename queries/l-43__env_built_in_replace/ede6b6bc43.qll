import cpp

/**
 * Environment Unit: Identifies expressions that likely refer to device or I/O memory.
 * These typically carry volatile qualifiers or specific kernel annotations indicating non-standard access semantics.
 */
predicate EnvironmentUnit(Expr target) {
  target.getType().hasQualifier("volatile") or
  target.getType().getName().matches("%_iomem%") or
  target.getType().getName().matches("%ioport%") or
  target.getType().getName().matches("%mmio%")
}

/**
 * Control Flow Unit: Verifies that an assignment inside a loop depends on the loop's induction variable,
 * forming a sequential access pattern over consecutive indices.
 */
predicate ControlFlowUnit(LoopStmt loop, ExprStmt stmt) {
  loop.getBody().getAChildRecursivelyOfKind(ExprStmt.class).contains(stmt) and
  stmt.getExpression() instanceof AssignmentExpr and
  exists(AssignmentExpr assign | 
    assign = stmt.getExpression() and
    (assign.getTarget() instanceof ArrayIndexingExpr or assign.getTarget() instanceof DerefExpr) and
    exists(assign.getTarget().getAChildOfType<Variable>()) and
    assign.getTarget().getAChildOfType<Variable>().getParent*().getAncestorOf(loop)
  )
}

/**
 * Root Cause Unit: Materializes the vulnerable pattern where a loop performs 
 * element-wise writes that compilers may optimize into bulk memory operations.
 */
class RootCauseUnit extends Stmt {
  RootCauseUnit() {
    exists(LoopStmt loop, ExprStmt stmt | 
      ControlFlowUnit(loop, stmt) and
      this = loop
    )
  }
}
