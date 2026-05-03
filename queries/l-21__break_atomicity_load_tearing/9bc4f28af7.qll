import cpp

/**
 * Captures the root cause: plain assignment to indirect memory access
 * without atomic or volatile protection. Matches the semantic family
 * of *ptr = val, arr[i] = val, ptr->field = val.
 */
class RootCauseUnit extends Expr {
  RootCauseUnit() {
    this instanceof AssignmentExpr and
    (this.getLeftOperand() instanceof DereferenceExpr or
     this.getLeftOperand() instanceof ArrayIndexingExpr or
     this.getLeftOperand() instanceof MemberAccessExpr) and
    not this instanceof CallExpr
  }

  /** Retrieves the underlying pointer/base expression for environment analysis */
  Expr getPointerSource() {
    result = this.getLeftOperand() instanceof DereferenceExpr ? this.getLeftOperand().getOperand() :
             this.getLeftOperand() instanceof ArrayIndexingExpr ? this.getLeftOperand().getBase() :
             this.getLeftOperand() instanceof MemberAccessExpr ? this.getLeftOperand().getReceiver() :
             none
  }
}

/**
 * Captures control flow context: ensures the assignment resides within a function scope.
 */
predicate controlFlowUnit(RootCauseUnit rcu) {
  exists(Function f | f.getScope().contains(rcu))
}

/**
 * Captures environment assumptions: the target points to shared/hardware memory,
 * indicated by the pointer originating from parameters, globals, or object members.
 */
predicate environmentUnit(RootCauseUnit rcu) {
  exists(Expr ptr | ptr = rcu.getPointerSource() |
    ptr instanceof Parameter or
    ptr instanceof GlobalVariable or
    ptr instanceof MemberAccessExpr
  )
}
