import cpp

/** 
 * Semantic Unit: Root Cause
 * Models structs that are likely to contain compiler-inserted padding due to alignment requirements.
 */
class StructWithImplicitPadding extends Class {
  StructWithImplicitPadding() { any() }
  
  /** Heuristic: Struct contains fields of different sizes that typically trigger alignment padding. */
  predicate hasPotentialPadding() {
    exists(Field f1, Field f2 |
      f1.getDeclaringType() = this and
      f2.getDeclaringType() = this and
      f1 != f2 and
      f1.getType().getSize() != f2.getType().getSize()
    )
  }
}

/** 
 * Semantic Unit: Control Flow
 * Captures individual field assignments to a specific struct instance.
 */
predicate assignsFieldIndividually(Expr target, Field f, Stmt stmt) {
  exists(ExprStmt es, Assignment assign, FieldAccess fa |
    es = stmt and
    es.getExpr() = assign and
    fa = assign.getLValue().(FieldAccess) and
    fa.getQualifier() = target and
    fa.getTarget() = f
  )
}

/** 
 * Semantic Unit: Environment & Exposure
 * Identifies operations that copy struct data to user-visible buffers.
 */
predicate copiesToUserSpace(Expr src, Expr dst) {
  exists(FunctionCall call |
    (call.getTarget().hasName("copy_to_user") or
     call.getTarget().hasName("memcpy") or
     call.getTarget().hasName("uinput_send_event")) and
    call.getArgument(0) = dst and
    call.getArgument(1) = src
  )
}

/** 
 * Semantic Unit: Initialization Gap
 * Ensures the struct instance was not initialized via a C99 designated initializer or aggregate initialization.
 */
predicate lacksAggregateInitialization(Expr target) {
  not exists(VariableAccess va, Variable v |
    va = target and
    va.getTarget() = v and
    v.hasInitializer() and
    v.getInitializer().isBraced()
  )
}
