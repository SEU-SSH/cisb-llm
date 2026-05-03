import cpp

/**
 * Semantic Unit: Root Cause
 * Identifies struct/union variables placed in a linker section that lack
 * an explicit alignment attribute, relying on compiler defaults.
 */
class RootCauseUnit extends Variable {
  RootCauseUnit() {
    (this.getType().hasName("struct") or this.getType().hasName("union"))
    and this.hasAttributeNamed("section")
    and not this.hasAttributeNamed("aligned")
    and this.isGlobalOrStatic()
  }

  predicate hasAttributeNamed(string name) {
    result = some Attribute attr | 
      attr.getParent() = this and 
      attr.getName().getStringValue() = name
  }

  predicate isGlobalOrStatic() {
    this.getScope().getEnclosingFunction().isEmpty()
  }
}

/**
 * Semantic Unit: Control Flow Assumption
 * Models the runtime behavior where the linker section containing these
 * variables is traversed as an array during initialization.
 */
predicate isTraversedAsArray(Variable v) {
  // Represents the assumption that runtime initialization code treats
  // the section as an array of structs.
  result = true
}

/**
 * Semantic Unit: Environment Assumption
 * Captures the compiler/environment context where default alignment settings
 * are assumed to differ from the developer's expectation.
 */
predicate assumesDefaultAlignmentShift() {
  // Represents environments where compiler default struct alignment
  // has changed or is not explicitly overridden.
  result = true
}
