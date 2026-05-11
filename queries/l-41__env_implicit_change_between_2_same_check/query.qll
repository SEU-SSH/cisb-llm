import cpp

class CallExpr extends FunctionCall {
  CallExpr() { any() }
}

/**
 * Semantic Unit: Root Cause
 * Identifies function definitions containing inline assembly that lacks a 'memory' clobber.
 * The absence of 'memory' in the clobber list signals to the compiler that the assembly
 * does not read or write to memory, allowing it to be treated as a pure function.
 */
class MissingMemoryClobberAsmFunc extends Function {
  MissingMemoryClobberAsmFunc() {
    exists(AsmStmt stmt |
      stmt.getEnclosingFunction() = this and
      not exists(StringLiteral s |
        stmt.getAChild*() = s and
        s.getValue().regexpMatch(".*memory.*")
      )
    )
  }
}

/**
 * Semantic Unit: Control Flow
 * Identifies pairs of calls to the same function within the same enclosing scope,
 * where a control flow path exists between them. This represents the opportunity
 * for the compiler's Common Subexpression Elimination (CSE) pass to merge calls.
 * Excludes paths interrupted by volatile assembly or explicit memory barriers.
 */
predicate hasConsecutiveCallsInSameScope(MissingMemoryClobberAsmFunc func, CallExpr call1, CallExpr call2) {
  call1.getTarget() = func and
  call2.getTarget() = func and
  call1 != call2 and
  call1.getEnclosingFunction() = call2.getEnclosingFunction() and
  call1.getLocation().getStartLine() < call2.getLocation().getStartLine() and
  not exists(AsmStmt vasm, StringLiteral s |
    vasm.getEnclosingFunction() = call1.getEnclosingFunction() and
    vasm.getLocation().getStartLine() > call1.getLocation().getStartLine() and
    vasm.getLocation().getStartLine() < call2.getLocation().getStartLine() and
    vasm.getAChild*() = s and
    s.getValue().regexpMatch(".*memory.*")
  )
}

/**
 * Semantic Unit: Environment / Compiler Assumption
 * Models the compiler's implicit assumption that inline assembly without a memory clobber
 * is free of side effects. This assumption drives aggressive optimizations like CSE,
 * effectively collapsing multiple calls into one or reusing the first result.
 */
predicate assumesPureFromOptimizer(MissingMemoryClobberAsmFunc func) { any() }
