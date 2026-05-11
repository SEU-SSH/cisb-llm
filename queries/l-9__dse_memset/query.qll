import cpp

class MemClearCall extends FunctionCall {
  MemClearCall() {
    this.getTarget().hasName("memset") or
    this.getTarget().hasName("bzero")
  }

  Expr getTargetExpr() { result = this.getArgument(0).getUnconverted() }

  Variable getTargetVar() {
    result = this.getTargetExpr().(VariableAccess).getTarget()
    or
    result =
      this.getTargetExpr().(AddressOfExpr).getOperand().getUnconverted().(VariableAccess).getTarget()
  }

  predicate isLocalVariableTarget() { this.getTargetVar() instanceof LocalVariable }

  private predicate isIgnorablePostClearUse(VariableAccess va) {
    exists(FunctionCall c |
      c.getAnArgument().getUnconverted() = va and
      (
        c.getTarget().hasName("free") or
        c.getTarget().hasName("kfree") or
        c.getTarget().hasName("vfree")
      )
    )
  }

  private predicate isAfterThis(Expr other) {
    other.getEnclosingFunction() = this.getEnclosingFunction() and
    other.getEnclosingStmt() != this.getEnclosingStmt() and
    (
      other.getLocation().getStartLine() > this.getLocation().getStartLine()
      or
      other.getLocation().getStartLine() = this.getLocation().getStartLine() and
      other.getLocation().getStartColumn() > this.getLocation().getStartColumn()
    )
  }

  predicate hasNoReadUntilScopeExit() {
    exists(LocalVariable v |
      v = this.getTargetVar() and
      not exists(VariableAccess va |
        va.getTarget() = v and
        va.isRValue() and
        this.isAfterThis(va) and
        not this.isIgnorablePostClearUse(va)
      )
    )
  }
}
