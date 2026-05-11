import cpp
import semmle.code.cpp.dataflow.DataFlow

/**
 * Environment Unit: Represents the implicit ABI/compiler assumption that
 * certain functions (like memset) return their first argument in the return register.
 * This assumption triggers the bug when violated by compiler optimizations.
 */
predicate environment_unit() { any() }

/**
 * Control Flow Unit: Models the data-flow constraint that the first argument's value
 * must be preserved to the return value across all control flow paths.
 * Returns true if there exists a path where the value is altered without restoration.
 */
predicate control_flow_unit(Function f, Parameter firstArg) {
  firstArg = f.getParameter(0) and
  exists(ReturnStmt ret, VariableAccess va |
    ret.getEnclosingFunction() = f and
    ret.hasExpr() and
    va.getTarget() = firstArg and
    DataFlow::localExprFlow(va, ret.getExpr())
  )
}

/**
 * Root Cause Unit: Identifies functions that expect to preserve the first argument
 * as the return value but fail to do so due to internal modifications.
 */
class RootCauseUnit extends Function {
  predicate preservesInitialArgValue() {
    exists(ReturnStmt ret, Expr retExpr |
      ret.getEnclosingFunction() = this and
      retExpr = ret.getExpr() and
      (
        exists(VariableAccess va |
          va = retExpr and
          va.getTarget() = this.getParameter(0)
        )
        or
        retExpr instanceof ThisExpr
      )
    )
  }

  /**
   * Checks if the function explicitly guarantees preservation of the first argument.
   * Functions failing this check are candidates for the CISB pattern.
   */
  RootCauseUnit() {
    exists(this.getParameter(0)) and
    not exists(ReturnStmt ret, Expr retExpr |
      ret.getEnclosingFunction() = this and
      retExpr = ret.getExpr() and
      (
        exists(VariableAccess va |
          va = retExpr and
          va.getTarget() = this.getParameter(0)
        )
        or
        retExpr instanceof ThisExpr
      )
    )
  }
}
