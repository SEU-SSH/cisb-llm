import cpp

/** 
 * Semantic Unit: Root Cause
 * Models structs that are likely to contain compiler-inserted padding due to alignment requirements.
 */
class StructWithImplicitPadding extends Class {
  StructWithImplicitPadding() {
    result = this;
  }
  
  /** Heuristic: Struct contains fields of different sizes that typically trigger alignment padding. */
  boolean hasPotentialPadding() {
    exists(Field f1, Field f2 |
      f1.getParentClass() = this and
      f2.getParentClass() = this and
      f1 != f2 and
      f1.getType().getSizeInBits() != f2.getType().getSizeInBits()
    )
  }
}

/** 
 * Semantic Unit: Control Flow
 * Captures individual field assignments to a specific struct instance.
 */
predicate assignsFieldIndividually(Expr target, Field f, Stmt stmt) {
  stmt instanceof AssignmentStmt and
  stmt.getTarget().getAnAccess() instanceof MemberAccess and
  cast<MemberAccess>(stmt.getTarget().getAnAccess()).getTarget() = target and
  cast<MemberAccess>(stmt.getTarget().getAnAccess()).getField() = f
}

/** 
 * Semantic Unit: Environment & Exposure
 * Identifies operations that copy struct data to user-visible buffers.
 */
predicate copiesToUserSpace(Expr src, Expr dst) {
  exists(CallExpr call |
    (call.getCallee().getName() = "copy_to_user" or
     call.getCallee().getName() = "memcpy" or
     call.getCallee().getName() = "uinput_send_event") and
    call.getArgument(0) = dst and
    call.getArgument(1) = src
  )
}

/** 
 * Semantic Unit: Initialization Gap
 * Ensures the struct instance was not initialized via a C99 designated initializer or aggregate initialization.
 */
predicate lacksAggregateInitialization(Expr target) {
  not exists(InitListExpr init |
    init.getInitValue() = target
  )
}
