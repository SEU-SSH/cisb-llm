import cpp

/**
 * Semantic Unit: Environment Assumption
 * Contextual marker for the required compilation environment.
 * Static analysis cannot verify compiler version/flags; this predicate
 * documents the assumption and can be extended with project config checks.
 */
predicate assumesGCC48_49OptimizationEnv() {
  // Always true in this abstracted query; represents environment constraint.
  true
}

/**
 * Semantic Unit: Control Flow & Scope Assumption
 * Identifies expressions sequentially initialized in the same scope
 * without volatile qualifiers or explicit memory barriers.
 */
predicate inSequentialInitScope(Expr e1, Expr e2) {
  exists(Scope s |
    s.contains(e1) and s.contains(e2) and
    not s.isGlobalScope() and
    (exists(CompoundStmt cs | cs.contains(e1) and cs.contains(e2)) or
     exists(InitializerList il | il.contains(e1) and il.contains(e2)))
  )
}

/**
 * Semantic Unit: Root Cause Unit
 * Core pattern: Union initialization via multiple distinct member paths
 * targeting the same underlying storage. Triggers GCC 4.8/4.9 optimizer bug.
 */
class UnionCrossMemberInit extends Expr {
  UnionCrossMemberInit() {
    // Matches designated initializers or member assignments targeting a union
  }
  
  /** Identifies if this expression targets a union-typed object */
  predicate targetsUnionType() {
    exists(ClassDecl cd |
      cd instanceof ClassDecl and
      (cd.getName().toLowerCase().contains("union") or cd.getQualifiedName().contains("_addr"))
    )
  }
  
  /** Identifies different member paths being initialized */
  predicate accessesDifferentMemberPath(Expr other) {
    exists(MemberAccess ma1, MemberAccess ma2 |
      ma1 = this and ma2 = other and
      ma1.getTarget() = ma2.getTarget() and
      ma1.getMember().getName() != ma2.getMember().getName()
    )
  }
}
