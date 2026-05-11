import cpp

/**
 * @brief Root cause unit: Identifies external variable declarations with implicit alignment > 1 byte
 * and lacking explicit alignment or packed attributes.
 */
class RootCauseUnit extends Variable {
  RootCauseUnit() {
    this.hasSpecifier("extern") and
    this.getType() instanceof IntegralType and
    this.getType().getSize() > 1 and
    not this.getAnAttribute().hasName("aligned") and
    not this.getAnAttribute().hasName("packed")
  }
}

/**
 * @brief Control flow unit: Represents memory accesses to variables matching the root cause.
 * The vulnerability manifests when these accesses are optimized by the compiler based on
 * the declared type's alignment, potentially causing unaligned access faults.
 */
class ControlFlowUnit extends VariableAccess {
  ControlFlowUnit() {
    this.getTarget() instanceof RootCauseUnit
  }
}

/**
 * @brief Environment unit: Captures the assumption of a strict-alignment architecture
 * where unaligned accesses trigger hardware faults.
 */
predicate environmentUnit() { any() }
