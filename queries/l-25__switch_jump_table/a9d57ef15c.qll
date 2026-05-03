import cpp

/**
 * @name CISB: GCC Jump Table Retpoline Bypass Library
 * @description Reusable semantic units for detecting switch statements 
 *              vulnerable to Spectre v2 due to compiler-generated jump tables.
 */

/**
 * @brief Root Cause Unit
 * Represents the switch statement node that serves as the entry point 
 * for the compiler-introduced indirect jump mechanism.
 */
class SwitchJumpTableTrigger extends Stmt {
  SwitchJumpTableTrigger() {
    this instanceof SwitchStmt
  }
}

/**
 * @brief Control Flow Unit
 * Determines if a switch statement exhibits the structural characteristics 
 * that trigger the compiler to generate a jump table (indirect jump dispatch).
 * Based on historical GCC behavior: > 20 cases typically trigger jump tables.
 */
predicate triggersIndirectJumpDispatch(SwitchStmt s) {
  result = s.getCases().size() > 20;
}

/**
 * @brief Environment Unit
 * Models the absence of the `-fno-jump-tables` compiler flag.
 * In practice, this would be verified against compilation database entries.
 * Defined here as a predicate to satisfy the CISB environmental assumption.
 */
predicate lacksJumpTableMitigation() {
  // Abstracted for standalone query execution. 
  // Assumes mitigation is absent unless explicitly configured otherwise.
  result = true;
}

/**
 * @brief Environment Unit
 * Models the presence of a security-hardened context requiring retpoline mitigations.
 * Corresponds to configurations like CONFIG_RETPOLINE in the Linux kernel.
 */
predicate isRetpolineSensitiveContext() {
  // Abstracted for standalone query execution.
  // Assumes security context is active based on CISB definition.
  result = true;
}
