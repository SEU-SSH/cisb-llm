import cpp

class CallExpr extends FunctionCall {
  CallExpr() { any() }
}

/**
 * Identifies Case nodes that lack explicit terminators, enabling implicit fall-through.
 */
class FallThroughCase extends SwitchCase {
  FallThroughCase() {
    not exists(BreakStmt b | this.getAChild*() = b) and
    not exists(ReturnStmt r | this.getAChild*() = r) and
    not exists(ContinueStmt c | this.getAChild*() = c) and
    not exists(ThrowExpr t | this.getAChild*() = t)
  }
}

/**
 * Represents a memory read or write operation in the AST.
 */
class MemoryAccess extends Expr {
  MemoryAccess() {
    this instanceof VariableAccess or
    this instanceof FieldAccess or
    this instanceof ArrayExpr or
    this instanceof PointerDereferenceExpr
  }
}

/**
 * Identifies expressions that perform address calculations (pointer arithmetic, offsets).
 */
predicate isAddressCalculation(Expr e) {
  (e instanceof AddExpr or e instanceof SubExpr) and
  e.getType() instanceof PointerType
}

/**
 * Checks if a node or its descendants contain compiler ordering barriers.
 */
predicate hasOrderingBarrier(Expr n) {
  exists(AsmStmt ia | n.getEnclosingStmt().getAChild*() = ia) or
  exists(CallExpr ce |
    (ce.getTarget().hasName("barrier") or ce.getTarget().hasName("barrier_var")) and
    n.getAChild*() = ce
  )
}

/**
 * Root cause unit: Switch statement with fall-through cases performing memory accesses
 * without isolation barriers, susceptible to compiler reordering/duplication of address calculations.
 */
class CISBSwitchFallThrough extends SwitchStmt {
  CISBSwitchFallThrough() {
    exists(FallThroughCase fc | this.getAChild*() = fc) and
    exists(MemoryAccess ma, FallThroughCase fc |
      fc.getAChild*() = ma and
      this.getAChild*() = fc
    ) and
    not exists(Expr addrCalc, MemoryAccess acc |
      isAddressCalculation(addrCalc) and
      this.getAChild*() = addrCalc and
      this.getAChild*() = acc and
      hasOrderingBarrier(acc)
    )
  }
}
