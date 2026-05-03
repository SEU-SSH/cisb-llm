import cpp

/**
 * Semantic Unit: Root Cause
 * Identifies function definitions containing inline assembly that lacks a 'memory' clobber.
 * The absence of 'memory' in the clobber list signals to the compiler that the assembly
 * does not read or write to memory, allowing it to be treated as a pure function.
 */
class MissingMemoryClobberAsmFunc extends FunctionDefinition {
  MissingMemoryClobberAsmFunc() {
    exists(InlineAsmStmt stmt | 
      this.getBody().getAChildPlusSome^() = stmt.getASR() |
      not stmt.getClobbers().contains("memory")
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
  call1.getTarget().getName() = func.getName() |
  call2.getTarget().getName() = func.getName() |
  call1 != call2 |
  call1.getEnclosingFunction() = call2.getEnclosingFunction() |
  exists(ControlFlowGraph cfg | cfg = call1.getEnclosingFunction().getControlFlowGraph() |
    cfg.hasReachable(call1.asr(), call2.asr()) |
    not exists(InlineAsmStmt vasm | vasm.isVolatile() | 
      cfg.hasReachable(call1.asr(), vasm.asr()) and cfg.hasReachable(vasm.asr(), call2.asr())
    )
  )
}

/**
 * Semantic Unit: Environment / Compiler Assumption
 * Models the compiler's implicit assumption that inline assembly without a memory clobber
 * is free of side effects. This assumption drives aggressive optimizations like CSE,
 * effectively collapsing multiple calls into one or reusing the first result.
 */
predicate assumesPureFromOptimizer(MissingMemoryClobberAsmFunc func) {
  // Represents the compiler's view: asm without 'memory' clobber => pure function
  true
}
