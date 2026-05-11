import cpp
import semmle.code.cpp.controlflow.Dominance

class InlineAsmStmt extends AsmStmt {
  InlineAsmStmt() { any() }
}

private predicate exprReferencesVariable(Expr e, Variable var) {
  exists(VariableAccess va |
    va.getTarget() = var and
    e.getAChild*() = va
  )
}

private predicate isNullLike(Expr e) {
  e.getValueText() = "0" or
  e.getValueText() = "NULL" or
  e.getType() instanceof NullPointerType
}

/**
 * @brief Root cause unit: Identifies inline assembly statements that contain a memory operand dereferencing a variable.
 * Matches patterns like *(T*)ptr or ptr->field inside asm blocks.
 */
predicate rootCauseUnit(InlineAsmStmt stmt, Variable var) {
  exists(PointerDereferenceExpr deref |
    stmt.getAChild*() = deref and
    exprReferencesVariable(deref.getOperand(), var)
  )
  or
  exists(PointerFieldAccess mem |
    stmt.getAChild*() = mem and
    exprReferencesVariable(mem.getQualifier(), var)
  )
}

/**
 * @brief Control flow unit: Identifies null checks on the same variable that are dominated by the inline asm statement.
 * Ensures the null check appears later in the execution order.
 */
predicate controlFlowUnit(InlineAsmStmt asmStmt, Variable var, IfStmt ifStmt) {
  asmStmt.getEnclosingFunction() = ifStmt.getEnclosingFunction() and
  dominates(asmStmt, ifStmt) and
  isNullCheck(ifStmt, var)
}

/**
 * @brief Helper: Determines if an IfStmt condition performs a null check on a given variable.
 * Normalizes across == NULL, != NULL, !ptr, and ptr < 0 forms.
 */
predicate isNullCheck(IfStmt ifStmt, Variable var) {
  exists(Expr cond |
    ifStmt.getCondition() = cond and
    (
      exists(ComparisonOperation cmp, VariableAccess va, Expr other |
        cmp = cond and
        (cmp.getOperator() = "==" or cmp.getOperator() = "!=" or
         cmp.getOperator() = "<" or cmp.getOperator() = ">") and
        cmp.hasOperands(va, other) and
        va.getTarget() = var and
        isNullLike(other)
      )
      or
      exists(NotExpr un, VariableAccess va |
        un = cond and
        va = un.getOperand() and
        va.getTarget() = var
      )
    )
  )
}

/**
 * @brief Environment unit: Documents the compiler optimization context required for this CISB.
 * Note: Static analysis cannot detect compiler flags at query time; this unit captures the necessary assumption.
 */
predicate environmentUnit() { any() }
