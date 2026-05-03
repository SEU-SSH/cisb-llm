import cpp
import DataFlow

/**
 * Semantic Unit 1: Root Cause
 * Captures the assignment of a shared memory field to a local variable
 * without a memory barrier or volatile qualifier.
 */
class RootCauseUnit extends AssignExpr {
  RootCauseUnit() {
    this.getOperand(1) instanceof MemberAccess
  }
  
  predicate isUnprotected() {
    not this.getOperand(1).toString().contains("ACCESS_ONCE") and
    not this.getOperand(1).toString().contains("READ_ONCE") and
    not this.getOperand(1).toString().contains("volatile")
  }
}

/**
 * Semantic Unit 2: Control Flow
 * Tracks the data flow from the cached variable to its usage in
 * null checks or dereferences, ensuring assignment precedes usage.
 */
class ControlFlowUnit extends Expr {
  ControlFlowUnit() {
    this instanceof Expr
  }
  
  predicate followsRootCause(RootCauseUnit rcu) {
    exists(DataFlow::exprNode(rcu.getOperand(1)) -> DataFlow::exprNode(this))
  }
  
  predicate isNullCheck() {
    this instanceof BinaryOperator and (
      this.getOperator() == "==" and this.getOperand(1).toString() == "0"
    ) or
    this instanceof UnaryOperator and this.getOperator() == "!"
  }
  
  predicate isNonNullCheck() {
    this instanceof BinaryOperator and (
      this.getOperator() == "!=" and this.getOperand(1).toString() == "0"
    )
  }
  
  predicate isDereference() {
    this instanceof UnaryOperator and this.getOperator() == "*"
  }
}

/**
 * Semantic Unit 3: Environment
 * Validates that the pattern occurs in a context where concurrent access
 * and compiler optimization could trigger the CISB.
 */
predicate environmentUnit(RootCauseUnit rcu, Expr cachedVar, Expr usage) {
  rcu.isUnprotected() and
  exists(Expr sharedRead, Expr actualCachedVar |
    sharedRead = rcu.getOperand(1) and
    actualCachedVar = rcu.getOperand(0) and
    cachedVar = actualCachedVar and
    exists(DataFlow::exprNode(sharedRead) -> DataFlow::exprNode(actualCachedVar) -> DataFlow::exprNode(usage)) and
    (usage.isNullCheck() or usage.isNonNullCheck() or usage.isDereference())
  )
}
