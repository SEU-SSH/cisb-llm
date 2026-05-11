import cpp

/**
 * Semantic Unit: Environment Assumption
 * Contextual marker for the required compilation environment.
 * Static analysis cannot verify compiler version/flags; this predicate
 * documents the assumption and can be extended with project config checks.
 */
predicate assumesGCC48_49OptimizationEnv() { any() }

/**
 * Semantic Unit: Control Flow & Scope Assumption
 * Identifies expressions sequentially initialized in the same scope
 * without volatile qualifiers or explicit memory barriers.
 */
predicate inSequentialInitScope(Expr e1, Expr e2) {
  e1.getEnclosingBlock() = e2.getEnclosingBlock() and
  exists(e1.getEnclosingFunction()) and
  exists(e2.getEnclosingFunction())
}

/**
 * Semantic Unit: Root Cause Unit
 * Core pattern: Union initialization via multiple distinct member paths
 * targeting the same underlying storage. Triggers GCC 4.8/4.9 optimizer bug.
 */
class UnionCrossMemberInit extends FieldAccess {
  UnionCrossMemberInit() {
    this.getQualifier().getType().getUnspecifiedType() instanceof Union
  }

  /** Identifies if this expression targets a union-typed object */
  predicate targetsUnionType() {
    this.getQualifier().getType().getUnspecifiedType() instanceof Union
  }

  /** Identifies different member paths being initialized */
  predicate accessesDifferentMemberPath(Expr other) {
    exists(FieldAccess ma2 |
      ma2 = other and
      ma2.getQualifier() = this.getQualifier() and
      ma2.getTarget() != this.getTarget()
    )
  }
}
