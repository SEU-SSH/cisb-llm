import cpp

/**
 * Identifies Case nodes that lack explicit terminators, enabling implicit fall-through.
 */
class FallThroughCase extends Case {
  FallThroughCase() {
    not exists(BreakStatement | ReturnStatement | ThrowStatement | ContinueStatement b |
      b.getParentNode* = this
    )
  }
}

/**
 * Represents a memory read or write operation in the AST.
 */
class MemoryAccess extends Expr {
  MemoryAccess() {
    this instanceof ReadExpr or this instanceof WriteExpr
  }
}

/**
 * Identifies expressions that perform address calculations (pointer arithmetic, offsets).
 */
predicate isAddressCalculation(Expr e) {
  e instanceof BinOp and (
    e.getOperator() = "+" or
    e.getOperator() = "-"
  ) and e.getType().isPointerType()
}

/**
 * Checks if a node or its descendants contain compiler ordering barriers.
 */
predicate hasOrderingBarrier(Node n) {
  exists(InlineAsm ia | ia.getParentNode* = n) or
  exists(CallExpr ce |
    ce.getTarget().getName() = "barrier" or
    ce.getTarget().getName() = "barrier_var" |
    ce.getParentNode* = n
  )
}

/**
 * Root cause unit: Switch statement with fall-through cases performing memory accesses
 * without isolation barriers, susceptible to compiler reordering/duplication of address calculations.
 */
class CISBSwitchFallThrough extends SwitchStatement {
  CISBSwitchFallThrough() {
    // Contains at least one fall-through case
    exists(FallThroughCase fc | fc.getParentNode* = this) and
    // Contains memory accesses in those cases
    exists(MemoryAccess ma, FallThroughCase fc |
      ma.getParentNode* = fc and
      fc.getParentNode* = this
    ) and
    // Lacks ordering barriers between address calculation and access within the switch body
    not exists(Expr addrCalc, MemoryAccess acc |
      isAddressCalculation(addrCalc) and
      acc.getParentNode* = this and
      hasOrderingBarrier(acc)
    )
  }
}
