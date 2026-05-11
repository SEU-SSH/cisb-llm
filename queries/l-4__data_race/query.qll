import cpp
import semmle.code.cpp.dataflow.DataFlow

/**
 * Semantic Unit 1: Root Cause
 * Captures the assignment of a shared memory field to a local variable
 * without a memory barrier or volatile qualifier.
 */
class RootCauseUnit extends AssignExpr {
  RootCauseUnit() { this.getRValue() instanceof FieldAccess }
}

private predicate isUnprotected(RootCauseUnit rcu) {
  not rcu.getRValue().toString().matches("%ACCESS_ONCE%") and
  not rcu.getRValue().toString().matches("%READ_ONCE%") and
  not rcu.getRValue().toString().matches("%volatile%")
}

private predicate isNullCheck(Expr e) {
  exists(EqualityOperation cmp, Expr other |
    cmp = e and
    cmp.hasOperands(_, other) and
    other.getValueText() = "0"
  )
  or
  e instanceof NotExpr
}

private predicate isNonNullCheck(Expr e) {
  exists(NEExpr cmp, Expr other |
    cmp = e and
    cmp.hasOperands(_, other) and
    other.getValueText() = "0"
  )
}

private predicate isDereference(Expr e) { e instanceof PointerDereferenceExpr }

/**
 * Semantic Unit 3: Environment
 * Validates that the pattern occurs in a context where concurrent access
 * and compiler optimization could trigger the CISB.
 */
predicate environmentUnit(RootCauseUnit rcu, Expr cachedVar, Expr usage) {
  isUnprotected(rcu) and
  cachedVar = rcu.getLValue() and
  DataFlow::localExprFlow(rcu.getRValue(), cachedVar) and
  DataFlow::localExprFlow(cachedVar, usage) and
  (isNullCheck(usage) or isNonNullCheck(usage) or isDereference(usage))
}
