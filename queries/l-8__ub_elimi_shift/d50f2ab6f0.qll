import cpp
import semmle.code.cpp.dataflow.DataFlow

/**
 * Semantic Unit: Root Cause
 * Identifies a shift amount that is derived from an unchecked source.
 */
predicate isUncheckedShiftAmount(Expr amount) {
  exists(ShiftExpr se | 
    se.getOperand(1) = amount and
    // Amount flows from a source
    exists(DataFlow::Node src | 
      src.hasFlowTarget(amount) and 
      src.isExternalSource() 
    ) and
    // No dominating statement validates the amount
    not exists(Stmt v | 
      v.dominates(se.getEnclosingStmt()) and 
      v.checksValue(amount) 
    )
  )
}

/**
 * Helper to detect validation of a value in a controlling statement.
 */
predicate checksValue(Stmt s, Expr val) {
  exists(IfStmt ifs | 
    ifs = s and 
    exists(ComparisonExpr comp | 
      ifs.getCondition().hasAncestor(comp) and 
      (comp.getLeftOperand() = val or comp.getRightOperand() = val)
    )
  )
}

/**
 * Semantic Unit: Control Flow & Environment
 * Identifies a statement that checks the result of a shift expression dominated by that shift.
 * The environment assumption is that the compiler optimizes based on UB of the unchecked amount.
 */
class CISBShiftCheckRemoval extends Stmt {
  CISBShiftCheckRemoval() {
    exists(IfStmt ifs | 
      ifs = this and 
      exists(Expr cond | 
        ifs.getCondition().hasAncestor(cond) and 
        exists(ShiftExpr se | 
          se.getOperand(0).getType().getName() = cond.getType().getName() and 
          cond.hasAncestor(se) and 
          se.getEnclosingStmt().dominates(ifs) and 
          isUncheckedShiftAmount(se.getOperand(1)) 
        )
      )
    )
  }
}
