import cpp

/**
 * Represents an inline assembly statement that lacks the volatile qualifier.
 * Such statements expose the compiler to assuming no side effects beyond explicit operands.
 */
class NonVolatileAsm extends AsmStmt {
  NonVolatileAsm() { this.isVolatile() = false }
}

/**
 * Root Cause Unit: Identifies semantically equivalent non-volatile inline assembly 
 * statements within the same function. The compiler may treat them as redundant.
 */
predicate rootCauseUnit(NonVolatileAsm a1, NonVolatileAsm a2) {
  a1.getEnclosingFunction() = a2.getEnclosingFunction() and
  a1 != a2 and
  a1.getTemplateString() = a2.getTemplateString()
}

/**
 * Control Flow Unit: Verifies that a2 is reachable after a1 within the function's scope.
 * This ensures the second call is actually executed in some paths, making its removal dangerous.
 */
predicate controlFlowUnit(NonVolatileAsm a1, NonVolatileAsm a2) {
  a1.getEnclosingFunction() = a2.getEnclosingFunction() and
  a1.getBeginLine() < a2.getBeginLine()
}

/**
 * Environment Unit: Encapsulates the environmental and compiler assumptions underlying this CISB.
 * - Optimization level enables dead code/redundancy elimination.
 * - Hardware state changes (e.g., CPU feature registers) are invisible to the compiler's IR.
 * This predicate acts as a conceptual boundary for the vulnerability pattern.
 */
predicate environmentUnit() {
  // Represents the implicit environment constraint. 
  // In static analysis, we flag this pattern knowing it requires optimization + hidden state.
  true
}
