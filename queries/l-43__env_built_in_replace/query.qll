import cpp

class AssignmentExpr extends AssignExpr {
  AssignmentExpr() { any() }
}

module BulkMemOpt {
  /**
   * Environment Unit: Identifies expressions that likely refer to device or I/O memory.
   * These typically carry volatile qualifiers or specific kernel annotations indicating non-standard access semantics.
   */
  predicate environmentUnit(Expr target) {
    target.getType().isVolatile() or
    target.getType().getName().matches("%_iomem%") or
    target.getType().getName().matches("%ioport%") or
    target.getType().getName().matches("%mmio%")
  }

  /**
   * Control Flow Unit: Verifies that an assignment inside a loop depends on the loop's induction variable,
   * forming a sequential access pattern over consecutive indices.
   */
  predicate controlFlowUnit(Loop loop, ExprStmt stmt) {
    exists(AssignmentExpr assign, VariableAccess va |
      loop.getStmt().getAChild*() = stmt and
      assign = stmt.getExpr() and
      (assign.getLValue() instanceof ArrayExpr or assign.getLValue() instanceof PointerDereferenceExpr) and
      assign.getLValue().getAChild*() = va and
      loop.getControllingExpr().getAChild*() = va
    )
  }

  /**
   * Root Cause Unit: Materializes the vulnerable pattern where a loop performs
   * element-wise writes that compilers may optimize into bulk memory operations.
   */
  class RootCauseUnit extends Loop {
    RootCauseUnit() {
      exists(ExprStmt stmt |
        controlFlowUnit(this, stmt)
      )
    }
  }
}
