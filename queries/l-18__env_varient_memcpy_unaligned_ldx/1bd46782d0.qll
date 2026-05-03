import cpp

/**
 * Environment Unit: Identifies functions operating in an IO memory context.
 * These functions typically handle device registers or mapped I/O regions where
 * standard memory alignment assumptions do not hold.
 */
predicate environmentUnit(Function f) {
  f.getName().getString().matches(".*_io$|ioread[0-9]+|iowrite[0-9]+|memcpy_toio|memcpy_fromio")
}

/**
 * Control Flow Unit: Captures the direct call relationship between an IO accessor
 * and a standard memory manipulation function.
 */
predicate controlFlowUnit(CallExpr call, Function caller, Function callee) {
  environmentUnit(caller) and
  (callee.getName().getString() = "memset" or callee.getName().getString() = "memcpy" or callee.getName().getString() = "__builtin_memset" or callee.getName().getString() = "__builtin_memcpy") and
  call.getTarget() = callee and
  call.getEnclosingFunction() = caller
}

/**
 * Root Cause Unit: Materializes the semantic root cause of the CISB.
 * The vulnerability arises because the compiler treats the callee as a standard builtin,
 * applying optimizations (e.g., alignment-based vectorization or loop unrolling) that
 * are unsafe for IO memory regions.
 */
predicate rootCauseUnit(CallExpr call, Function caller, Function callee) {
  controlFlowUnit(call, caller, callee)
}
