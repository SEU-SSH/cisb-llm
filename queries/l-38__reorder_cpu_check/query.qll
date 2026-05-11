import cpp

/**
 * Root Cause Unit: Captures inline assembly statements that lack a 'memory' clobber constraint.
 * Without this constraint, the compiler assumes the assembly does not affect global memory state
 * and may freely reorder it relative to other operations.
 */
class UnsafeInlineAsm extends AsmStmt {
  UnsafeInlineAsm() {
    not exists(StringLiteral s |
      this.getAChild*() = s and
      s.getValue().regexpMatch(".*memory.*")
    )
  }
}

/**
 * Control Flow Unit: Identifies inline assembly that is syntactically placed within a conditional block.
 * Models the developer's expectation that the condition guards the assembly execution.
 * Note: Syntactic nesting does not guarantee semantic ordering under compiler optimizations.
 */
predicate isSyntacticallyGuarded(UnsafeInlineAsm asmStmt) {
  exists(IfStmt guard |
    guard.getThen().getAChild*() = asmStmt
    or
    guard.getElse().getAChild*() = asmStmt
  )
}

/**
 * Environment Unit: Captures the assumption that the code interacts with hardware features
 * or architecture-specific instructions that require strict execution ordering.
 * Filters for patterns commonly associated with coprocessor access or hardware capability checks.
 */
predicate targetsHardwareWithConditionalSupport(UnsafeInlineAsm asmStmt) {
  exists(StringLiteral s |
    asmStmt.getAChild*() = s and
    s.getValue().regexpMatch("(?i).*(mrc|mcr|cp15|hardware|capability|smp|barrier).*")
  )
}
