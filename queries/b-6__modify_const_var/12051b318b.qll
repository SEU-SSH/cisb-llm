import cpp

/**
 * Environment Unit: Variables marked 'const' but not 'volatile'.
 * The compiler assumes these are immutable.
 */
class ConstEnvironmentVar extends Variable {
  ConstEnvironmentVar() {
    hasType(t | t.hasQualifier("const") and not t.hasQualifier("volatile"))
  }
}

/**
 * Control Flow Unit: Ensures the expression is within a reachable execution context.
 * Filters out declarations or unreachable code blocks.
 */
predicate controlFlowUnit(Expr e) {
  e.getEnclosingNode(FunctionBody()) != null or
  e.getEnclosingNode(GlobalScope()) != null
}

/**
 * Root Cause Unit: Identifies writes to a const variable through a cast that drops const.
 * Captures the undefined behavior that compilers exploit for optimization.
 */
predicate rootCauseUnit(Expr writeTarget, ConstEnvironmentVar cv) {
  exists(CastExpr c |
    writeTarget.getAnExpression*() = c and
    c.getType().hasQualifier("const") = false and
    c.getSource().getType().hasQualifier("const") and
    c.getSource() instanceof AddressOf and
    c.getSource().getOperand() = cv
  )
}
