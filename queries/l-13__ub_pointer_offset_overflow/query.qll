import cpp

class MemberAddressExpr extends AddressOfExpr {
  MemberAddressExpr() { this.getOperand() instanceof FieldAccess }

  predicate getField(Field f) { this.getOperand().(FieldAccess).getTarget() = f }
}

predicate isInLoopCondition(Expr e) {
  exists(Loop loop | loop.getControllingExpr() = e)
}

predicate hasPositiveOffset(Field f) {
  f.getByteOffset() > 0
}

private predicate isNullLike(Expr e) {
  e.getValueText() = "0" or
  e.getValueText() = "NULL" or
  e.getType() instanceof NullPointerType
}

class VulnerableMemberCheck extends Expr {
  VulnerableMemberCheck() {
    exists(MemberAddressExpr mae |
      (
        this instanceof NEExpr and
        this.(NEExpr).hasOperands(mae, any(Expr other | isNullLike(other)))
      )
      or
      exists(NotExpr ne, EQExpr eq, Expr other |
        ne = this and
        ne.getOperand() = eq and
        eq.hasOperands(mae, other) and
        isNullLike(other)
      )
    )
  }
}
