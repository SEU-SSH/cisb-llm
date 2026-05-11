import cpp

/**
 * Environment Unit: Variables marked 'const' but not 'volatile'.
 * The compiler assumes these are immutable.
 */
class ConstEnvironmentVar extends Variable {
  ConstEnvironmentVar() { this.isConst() and not this.isVolatile() }
}

/**
 * Control Flow Unit: Ensures the expression is within a reachable execution context.
 * Filters out declarations or unreachable code blocks.
 */
predicate controlFlowUnit(Expr e) {
  exists(Function f | f = e.getEnclosingFunction())
}

/**
 * Root Cause Unit: Identifies writes to a const variable through a cast that drops const.
 * Captures the undefined behavior that compilers exploit for optimization.
 */
predicate rootCauseUnit(Expr writeTarget, ConstEnvironmentVar cv) {
  exists(AssignExpr assign, Cast c, AddressOfExpr addr, VariableAccess va, PointerType castType |
    writeTarget = assign.getLValue() and
    c.getParentWithConversions*() = writeTarget and
    addr.getConversion+() = c and
    addr.getOperand().getUnconverted() = va and
    va.getTarget() = cv and
    addr.getType().getUnspecifiedType().(PointerType).getBaseType().isConst() and
    castType = c.getType().getUnspecifiedType() and
    not castType.getBaseType().isConst()
  )
}
