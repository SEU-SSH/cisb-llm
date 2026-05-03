import cpp

/**
 * Root Cause Unit: Identifies assignments to struct fields where the RHS 
 * involves tagged pointer computation (bitwise OR or cast) representing 
 * a pointer + flag combination.
 */
predicate root_cause_unit(AssignExpr e) {
  exists(MemberAccess ma | ma = e.getLeftOperand().(MemberAccess) |
    exists(Expression rhs | rhs = e.getRightOperand() |
      (rhs instanceof BitwiseOrExpr or rhs instanceof AddExpr or rhs instanceof CPlusPlusCastExpr)
    )
  )
}

/**
 * Control Flow Unit: Ensures the assignment is within a single function's scope
 * and follows the value computation, matching the assumption that the bug 
 * manifests within the same function performing the store.
 */
predicate control_flow_unit(AssignExpr e) {
  exists(Function f | f = e.getEnclosingFunction() |
    e.getEnclosingNode() instanceof FunctionBody
  )
}

/**
 * Environment Unit: Models the environment assumption that the compiler permits
 * store tearing for non-atomic/non-volatile types on architectures supporting
 * concurrent memory access. Excludes explicitly protected stores.
 */
predicate environment_unit(AssignExpr e) {
  not e.getType().isVolatileQualified() and
  not e.getType().isAtomicQualified()
}
