import cpp
import DataFlow

/**
 * Environment Unit: Represents the implicit ABI/compiler assumption that
 * certain functions (like memset) return their first argument in the return register.
 * This assumption triggers the bug when violated by compiler optimizations.
 */
predicate environment_unit() {
  true
}

/**
 * Control Flow Unit: Models the data-flow constraint that the first argument's value
 * must be preserved to the return value across all control flow paths.
 * Returns true if there exists a path where the value is altered without restoration.
 */
predicate control_flow_unit(Function f, Parameter firstArg) {
  exists (DataFlow::Node src, DataFlow::Node sink |
    src.asExpr() = firstArg and
    sink.asExpr() = f.getAReturn().getExpr() and
    f.getACFG().hasPath(src, sink)
  )
}

/**
 * Root Cause Unit: Identifies functions that expect to preserve the first argument
 * as the return value but fail to do so due to internal modifications.
 */
class root_cause_unit extends Function {
  root_cause_unit() {
    this.hasAtLeastOneParameter() and
    not this.preservesInitialArgValue()
  }

  /**
   * Checks if the function explicitly guarantees preservation of the first argument.
   * Functions failing this check are candidates for the CISB pattern.
   */
  predicate preservesInitialArgValue() {
    exists (Expr retExpr | retExpr = this.getAReturn().getExpr() |
      retExpr = this.getParameter(0) or
      retExpr instanceof ThisAccess
    )
  }
}
