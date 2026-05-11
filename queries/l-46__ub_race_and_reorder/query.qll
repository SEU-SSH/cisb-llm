import cpp

/**
 * Root Cause Unit: Identifies assignments to struct fields where the RHS 
 * involves tagged pointer computation (bitwise OR or cast) representing 
 * a pointer + flag combination.
 */
predicate root_cause_unit(AssignExpr e) {
  exists(FieldAccess ma | ma = e.getLValue().(FieldAccess) |
    exists(Expr rhs | rhs = e.getRValue() |
      (rhs instanceof BitwiseOrExpr or rhs instanceof AddExpr or rhs instanceof Cast)
    )
  )
}

/**
 * Control Flow Unit: Ensures the assignment is within a single function's scope
 * and follows the value computation, matching the assumption that the bug 
 * manifests within the same function performing the store.
 */
predicate control_flow_unit(AssignExpr e) {
  exists(e.getEnclosingFunction())
}

/**
 * Environment Unit: Models the environment assumption that the compiler permits
 * store tearing for non-atomic/non-volatile types on architectures supporting
 * concurrent memory access. Excludes explicitly protected stores.
 */
predicate environment_unit(AssignExpr e) {
  not e.getLValue().getType().isVolatile() and
  not e.getLValue().getType().getName().matches("%atomic%")
}
