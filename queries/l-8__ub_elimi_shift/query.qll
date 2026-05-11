import cpp
import semmle.code.cpp.controlflow.Dominance

/**
 * Semantic Unit: Root Cause
 * Identifies a shift amount that is derived from an unchecked source.
 */
predicate isUncheckedShiftAmount(Expr amount) {
  (
    exists(LShiftExpr se | se.getRightOperand() = amount) or
    exists(RShiftExpr se | se.getRightOperand() = amount)
  ) and
  not exists(Stmt v | checksValue(v, amount))
}

/**
 * Helper to detect validation of a value in a controlling statement.
 */
predicate checksValue(Stmt s, Expr val) {
  exists(IfStmt ifs, ComparisonOperation comp |
    ifs = s and
    ifs.getCondition().getAChild*() = comp and
    (comp.getLeftOperand() = val or comp.getRightOperand() = val)
  )
}

/**
 * Semantic Unit: Control Flow & Environment
 * Identifies a statement that checks the result of a shift expression dominated by that shift.
 * The environment assumption is that the compiler optimizes based on UB of the unchecked amount.
 */
class CISBShiftCheckRemoval extends IfStmt {
  CISBShiftCheckRemoval() {
    exists(Expr cond, BinaryBitwiseOperation se |
      this.getCondition() = cond and
      cond.getAChild*() = se and
      (se instanceof LShiftExpr or se instanceof RShiftExpr) and
      exists(IfStmt earlier |
        earlier.getLocation().getStartLine() <= this.getLocation().getStartLine() and
        earlier.getLocation().getStartLine() = se.getEnclosingStmt().getLocation().getStartLine()
      ) and
      isUncheckedShiftAmount(se.getRightOperand())
    )
  }
}
