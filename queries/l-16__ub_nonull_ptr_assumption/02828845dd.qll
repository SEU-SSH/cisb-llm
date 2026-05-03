import cpp

/**
 * @brief Root cause unit: Identifies inline assembly statements that contain a memory operand dereferencing a variable.
 * Matches patterns like *(T*)ptr or ptr->field inside asm blocks.
 */
predicate rootCauseUnit(InlineAsmStmt stmt, Variable var) {
  exists(DerefExpr deref |
    stmt.getAnExpression().getAChildPlus*() = deref and
    deref.getOperand() instanceof CastExpr and
    deref.getOperand().getAChildPlus*() = var.toExpr()
  )
  or
  exists(MemberAccessExpr mem |
    stmt.getAnExpression().getAChildPlus*() = mem and
    mem.getTarget().getAChildPlus*() = var.toExpr()
  );
}

/**
 * @brief Control flow unit: Identifies null checks on the same variable that are dominated by the inline asm statement.
 * Ensures the null check appears later in the execution order.
 */
predicate controlFlowUnit(InlineAsmStmt asmStmt, Variable var, IfStmt ifStmt) {
  asmStmt.getEnclosingFunction() = ifStmt.getEnclosingFunction() and
  cfgDominates(asmStmt, ifStmt) and
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
      exists(BinaryExpr bin |
        cond = bin and
        (bin.getOperator() = "==" or bin.getOperator() = "!=" or bin.getOperator() = "<" or bin.getOperator() = ">") and
        (bin.getLeftOperand() = var.toExpr() or bin.getRightOperand() = var.toExpr()) and
        (bin.getLeftOperand() != var.toExpr() ? bin.getLeftOperand().getType().isNull() : bin.getRightOperand().getType().isNull())
      )
      or
      exists(UnaryExpr un |
        cond = un and
        un.getOperator() = "!" and
        un.getOperand() = var.toExpr()
      )
    )
  );
}

/**
 * @brief Environment unit: Documents the compiler optimization context required for this CISB.
 * Note: Static analysis cannot detect compiler flags at query time; this unit captures the necessary assumption.
 */
predicate environmentUnit() {
  // Requires GCC with -fdelete-null-pointer-checks enabled (default in -O2, -O3, -Os).
  true
}
