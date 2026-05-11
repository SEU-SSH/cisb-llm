import cpp

class AssignmentExpr extends AssignExpr {
  AssignmentExpr() { any() }
}

class DereferenceExpr extends PointerDereferenceExpr {
  DereferenceExpr() { any() }
}

class ArrayIndexingExpr extends ArrayExpr {
  ArrayIndexingExpr() { any() }
}

class MemberAccessExpr extends FieldAccess {
  MemberAccessExpr() { any() }
}

class CallExpr extends FunctionCall {
  CallExpr() { any() }
}

/**
 * Captures the root cause: plain assignment to indirect memory access
 * without atomic or volatile protection. Matches the semantic family
 * of *ptr = val, arr[i] = val, ptr->field = val.
 */
class RootCauseUnit extends AssignmentExpr {
  RootCauseUnit() {
    this.getLValue() instanceof DereferenceExpr or
    this.getLValue() instanceof ArrayIndexingExpr or
    this.getLValue() instanceof MemberAccessExpr
  }
}

/** Retrieves the underlying pointer/base expression for environment analysis. */
predicate getPointerSource(RootCauseUnit rcu, Expr ptr) {
  ptr = rcu.getLValue().(DereferenceExpr).getOperand() or
  ptr = rcu.getLValue().(ArrayIndexingExpr).getArrayBase() or
  ptr = rcu.getLValue().(MemberAccessExpr).getQualifier()
}

/**
 * Captures control flow context: ensures the assignment resides within a function scope.
 */
predicate controlFlowUnit(RootCauseUnit rcu) {
  exists(rcu.getEnclosingFunction())
}

/**
 * Captures environment assumptions: the target points to shared/hardware memory,
 * indicated by the pointer originating from parameters, globals, or object members.
 */
predicate environmentUnit(RootCauseUnit rcu) {
  exists(Expr ptr |
    getPointerSource(rcu, ptr) and
    (
      exists(VariableAccess va |
        va = ptr and
        (va.getTarget() instanceof Parameter or va.getTarget() instanceof GlobalVariable)
      )
      or
      ptr instanceof MemberAccessExpr
    )
  )
}
