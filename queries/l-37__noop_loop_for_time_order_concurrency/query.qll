import cpp

/**
 * @brief Root cause unit: Identifies loops with effectively empty bodies and non-volatile control variables.
 */
class RootCauseUnit extends Loop {
  RootCauseUnit() {
    exists(Stmt body |
      body = this.getStmt() and
      not exists(FunctionCall c | body.getAChild*() = c) and
      not exists(Assignment a | body.getAChild*() = a) and
      not exists(CrementOperation c | body.getAChild*() = c)
    ) and
    not exists(VariableAccess va |
      this.getAChild*() = va and
      va.getTarget().getType().isVolatile()
    )
  }

  predicate hasEmptyOrSideEffectFreeBody() {
    exists(Stmt body |
      body = this.getStmt() and
      not exists(FunctionCall c | body.getAChild*() = c) and
      not exists(Assignment a | body.getAChild*() = a) and
      not exists(CrementOperation c | body.getAChild*() = c)
    )
  }

  predicate hasNonVolatileVariables() {
    not exists(VariableAccess va |
      this.getAChild*() = va and
      va.getTarget().getType().isVolatile()
    )
  }
}

/**
 * @brief Control flow unit: Ensures the loop is reachable and within the same function scope.
 */
class ControlFlowUnit extends RootCauseUnit {
  ControlFlowUnit() { exists(this.getEnclosingFunction()) }
}

/**
 * @brief Environment unit: Models the assumption of an optimizing compiler build.
 */
class EnvironmentUnit extends string {
  EnvironmentUnit() { this = "optimization-enabled" }
}
