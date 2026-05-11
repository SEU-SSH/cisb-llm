import cpp
import semmle.code.cpp.dataflow.DataFlow

/**
 * @name root_cause_unit
 * @description Identifies direct reads of shared variables (globals/struct fields)
 *              without atomic/volatile wrappers, representing the semantic root cause.
 */
predicate root_cause_unit(Expr e) {
  (
    exists(VariableAccess va |
      va = e and
      va.getTarget() instanceof GlobalVariable
    )
    or
    e instanceof FieldAccess
  ) and
  not isProtectedBySync(e)
}

predicate isProtectedBySync(Expr e) {
  exists(FunctionCall c |
    c.getTarget().hasName(["READ_ONCE", "ACCESS_ONCE", "atomic_read"]) and
    c.getArgument(0) = e
  )
  or
  exists(Cast c |
    c = e.getParent*() and
    c.getType().isVolatile()
  )
}

/**
 * @name control_flow_unit
 * @description Ensures the unsynchronized read value flows into a sink,
 *              such as a function call argument or conditional branch.
 */
predicate control_flow_unit(Expr src, Expr sink) {
  DataFlow::localExprFlow(src, sink) and
  (
    exists(FunctionCall fc | fc.getArgument(0) = sink)
    or
    exists(IfStmt i | i.getCondition() = sink)
  )
}

/**
 * @name environment_unit
 * @description Models the assumption that the accessed variable is shared across
 *              multiple execution contexts (e.g., kernel SMP, interrupt vs process).
 */
predicate environment_unit(Expr e) {
  exists(VariableAccess va |
    va = e and
    va.getTarget() instanceof GlobalVariable
  )
  or
  e instanceof FieldAccess
}
