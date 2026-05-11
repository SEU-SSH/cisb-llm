import cpp
import semmle.code.cpp.dataflow.DataFlow

module VulnerableCISBPattern {
  class GlobalOrStaticVariable extends Variable {
    GlobalOrStaticVariable() {
      this instanceof GlobalVariable or this.hasSpecifier("static")
    }
  }

  /**
   * Root cause unit: Stores targeting global or static variables.
   * These represent shared memory locations susceptible to visibility/race issues.
   */
  class SharedMemoryStore extends Expr {
    SharedMemoryStore() {
      exists(AssignExpr assign, VariableAccess va, GlobalOrStaticVariable target |
        this = assign and
        assign.getLValue().getAChild*() = va and
        va.getTarget() = target
      )
    }
  }

  /**
   * Control flow unit: Guards a store with a condition.
   * Models the source-level branching structure that compilers may flatten.
   */
  predicate isGuardedByCondition(Expr store, Expr cond) {
    exists(IfStmt ifStmt |
      ifStmt.getCondition() = cond and
      ifStmt.getThen().getAChild*() = store
    )
  }

  /**
   * Environment/Data flow unit: Condition depends on a synchronization variable.
   * Establishes the shared-state dependency required for the CISB trigger.
   */
  predicate dependsOnSyncVariable(Expr cond, Variable syncVar) {
    exists(VariableAccess va |
      va.getTarget() = syncVar and
      DataFlow::localExprFlow(va, cond)
    )
  }

  /**
   * Composed CISB pattern: Conditional store to shared memory gated by sync state.
   */
  predicate isVulnerableConditionalSharedStore(Expr store, Expr cond, Variable syncVar) {
    store instanceof SharedMemoryStore and
    isGuardedByCondition(store, cond) and
    dependsOnSyncVariable(cond, syncVar)
  }
}
