import cpp

/**
 * @name root_cause_unit
 * @description Identifies direct reads of shared variables (globals/struct fields) 
 *              without atomic/volatile wrappers, representing the semantic root cause.
 */
predicate root_cause_unit(Expr e) {
  (e instanceof GlobalVariable or e instanceof FieldAccess or e instanceof MemberAccess)
  and not isProtectedBySync(e)
}

boolean isProtectedBySync(Expr e) {
  exists(CallExpr c |
    c.getCalleeDeclaration().getName().regexp("^(READ_ONCE|ACCESS_ONCE|atomic_read)$") and
    c.getArgument(0) = e
  )
  or exists(CastExpr c | c.getType().isVolatile())
}

/**
 * @name control_flow_unit
 * @description Ensures the unsynchronized read value flows into a sink,
 *              such as a function call argument or conditional branch.
 */
predicate control_flow_unit(Expr src, Expr sink) {
  DataFlow::simpleFlow(DataFlow::exprNode(src), DataFlow::exprNode(sink))
  and (
    exists(FunctionCall fc | fc.getArgument(0) = sink)
    or exists(IfStmt i | i.getCondition() = sink)
  )
}

/**
 * @name environment_unit
 * @description Models the assumption that the accessed variable is shared across 
 *              multiple execution contexts (e.g., kernel SMP, interrupt vs process).
 */
predicate environment_unit(Expr e) {
  exists(GlobalVariable gv | gv.getAChild*() = e)
  or exists(FieldAccess fa | fa.getTarget().getAChild*() = e)
}
