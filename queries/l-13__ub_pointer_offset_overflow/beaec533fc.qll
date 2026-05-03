import cpp

class MemberAddressExpr extends Expr {
  MemberAddressExpr() {
    // Matches &ptr->field or &(*ptr).field
    exists(Assignable addr | addr = this and addr instanceof AddrOfExpr |
      addr.getOperand() instanceof MemberExpr
    )
  }

  predicate getField(out Field f) {
    exists(Assignable addr | addr = this and addr instanceof AddrOfExpr |
      addr.getOperand() instanceof MemberExpr me |
      f = me.getField()
    )
  }
}

predicate isInLoopCondition(Expr e) {
  exists(Stmt s | s.getParent*().getParent*() instanceof CompoundStmt |
    (s instanceof ForStmt and s.getCondition() = e) or
    (s instanceof WhileStmt and s.getCondition() = e) or
    (s instanceof DoStmt and s.getCondition() = e)
  )
}

predicate hasPositiveOffset(Field f) {
  f.getOffset() > 0
}

class VulnerableMemberCheck extends Expr {
  VulnerableCheck() {
    // The check is a comparison involving a MemberAddressExpr
    exists(MemberAddressExpr mae | mae = this.getAnOperand() |
      // Check for != NULL or != 0
      (this instanceof ComparisonExpr ce |
        ce.getOperator() = "!=" and
        ce.getOperand(0) = mae or ce.getOperand(1) = mae |
        ce.getOperand(0) = null or ce.getOperand(1) = null or
        ce.getOperand(0) = integerLiteral(0) or ce.getOperand(1) = integerLiteral(0)
      ) or
      // Check for !(&mae == NULL)
      (this instanceof UnaryExpr ue |
        ue.getOperator() = "!" and
        ue.getOperand() instanceof ComparisonExpr ce |
        ce.getOperator() = "==" and
        (ce.getOperand(0) = mae or ce.getOperand(1) = mae) |
        ce.getOperand(0) = null or ce.getOperand(1) = null
      )
    )
  }
}
