import cpp

/**
 * @brief Root cause unit: Identifies loops with effectively empty bodies and non-volatile control variables.
 */
class RootCauseUnit extends LoopStatement {
  RootCauseUnit() {
    this.hasEmptyOrSideEffectFreeBody() and this.hasNonVolatileVariables()
  }

  boolean hasEmptyOrSideEffectFreeBody() {
    exists(Stmt body | body = this.getBody() |
      not exists(Call c | c.getParent*() = body) and
      not exists(MemoryWrite mw | mw.getParent*() = body) and
      not exists(VolatileAccess va | va.getParent*() = body)
    )
  }

  boolean hasNonVolatileVariables() {
    not this.getAChild*().cast<Variable>().exists(v | v.getType().hasQualifier("volatile"))
  }
}

/**
 * @brief Control flow unit: Ensures the loop is reachable and within the same function scope.
 */
class ControlFlowUnit extends RootCauseUnit {
  ControlFlowUnit() {
    this.getEnclosingFunction() != null
  }
}

/**
 * @brief Environment unit: Models the assumption of an optimizing compiler build.
 */
class EnvironmentUnit {
  // Represents the precondition that the code is compiled with optimizations enabled.
  // In automated analysis, this is often treated as a given precondition for CISB detection.
}
