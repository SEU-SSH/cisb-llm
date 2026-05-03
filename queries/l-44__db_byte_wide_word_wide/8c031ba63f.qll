import cpp

/**
 * @brief Root cause unit: Identifies external variable declarations with implicit alignment > 1 byte
 * and lacking explicit alignment or packed attributes.
 */
class RootCauseUnit extends VariableDecl {
  RootCauseUnit() {
    this.getStorageClass() = StorageClass.Extern
    and this.hasImplicitAlignmentGreaterThanOne()
    and not this.hasExplicitAlignmentOrPackedAttribute()
  }

  boolean hasImplicitAlignmentGreaterThanOne() {
    // Types larger than 1 byte typically imply natural alignment > 1
    this.getType() instanceof IntegerType and this.getType().getSize() > 1
  }

  boolean hasExplicitAlignmentOrPackedAttribute() {
    this.hasAttribute("aligned") or this.hasAttribute("packed")
  }
}

/**
 * @brief Control flow unit: Represents memory accesses to variables matching the root cause.
 * The vulnerability manifests when these accesses are optimized by the compiler based on
 * the declared type's alignment, potentially causing unaligned access faults.
 */
class ControlFlowUnit extends Expr {
  ControlFlowUnit() {
    exists(RootCauseUnit v |
      this instanceof VarAccessExpr and
      this.getVariable() = v
    )
  }
}

/**
 * @brief Environment unit: Captures the assumption of a strict-alignment architecture
 * where unaligned accesses trigger hardware faults.
 */
boolean EnvironmentUnit() {
  // Represents the architectural constraint assumption.
  // In real-world usage, constrain this with target architecture macros (e.g., __hppa__).
  result = true
}
