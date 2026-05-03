import cpp

/**
 * Root Cause Unit: Captures inline assembly statements that lack a 'memory' clobber constraint.
 * Without this constraint, the compiler assumes the assembly does not affect global memory state
 * and may freely reorder it relative to other operations.
 */
class UnsafeInlineAsm extends InlineAsm {
  UnsafeInlineAsm() {
    // Check that 'memory' is not present in the clobber list
    not getClobbers().contains("memory")
  }
  
  /** Returns true if this assembly explicitly requests a memory barrier via clobber */
  boolean hasMemoryBarrier() { result = getClobbers().contains("memory"); }
}

/**
 * Control Flow Unit: Identifies inline assembly that is syntactically placed within a conditional block.
 * Models the developer's expectation that the condition guards the assembly execution.
 * Note: Syntactic nesting does not guarantee semantic ordering under compiler optimizations.
 */
predicate isSyntacticallyGuarded(UnsafeInlineAsm asm) {
  exists(ASTNode guard | 
    guard instanceof IfStmt and
    guard.getASTChild*().*(Expr*).getASourceNode() = asm.getASTSource()
  )
}

/**
 * Environment Unit: Captures the assumption that the code interacts with hardware features
 * or architecture-specific instructions that require strict execution ordering.
 * Filters for patterns commonly associated with coprocessor access or hardware capability checks.
 */
predicate targetsHardwareWithConditionalSupport(UnsafeInlineAsm asm) {
  // Matches common identifiers/instructions for ARM coprocessor access or SMP checks
  asm.getASMString().regexpMatch("(?i)(mrc|mcr|cp15|hardware|capability|smp|barrier)")
}
