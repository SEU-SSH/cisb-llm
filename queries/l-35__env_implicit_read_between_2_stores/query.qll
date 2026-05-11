import cpp
import semmle.code.cpp.controlflow.Dominance

class RootCauseUnit extends AsmStmt {
  RootCauseUnit() {
    not exists(StringLiteral s |
      this.getAChild*() = s and
      s.getValue().regexpMatch(".*memory.*")
    ) and
    exists(Expr e |
      this.getAChild*() = e and
      e.getType() instanceof PointerType
    )
  }
}

class ControlFlowUnit extends Expr {
  ControlFlowUnit() {
    this instanceof AssignExpr or this instanceof FunctionCall
  }

  /** Checks if this write operation dominates the root cause inline assembly. */
  predicate dominates(RootCauseUnit asmStmt) {
    dominates(this.getEnclosingStmt(), asmStmt)
  }
}

/**
 * Captures the environment assumption: the code is compiled under conditions where
 * optimization allows reordering or elimination of memory accesses based on inline
 * assembly clobber analysis.
 */
predicate environment_unit() { any() }
