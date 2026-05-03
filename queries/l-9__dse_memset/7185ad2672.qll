import cpp

class MemClearCall extends Call {
  MemClearCall() {
    getTarget().getName().matches("%memset%") 
      or getTarget().getName().matches("%explicit_bzero%")
      or getTarget().getName().matches("%bzero%")
  }

  /**
   * Checks if the first argument (target buffer) refers to a local variable.
   */
  predicate isLocalVariableTarget() {
    exists(Expr target | target = getArgument(0) | 
      target.asA<VariableAccess>() != null and
      target.asA<VariableAccess>().getVariable().hasType(LocalVariable())
    )
  }

  /**
   * Retrieves the expression representing the target buffer.
   */
  Expr getTargetExpr() {
    result = getArgument(0)
  }

  /**
   * Checks if the target variable is never read between this call and the end of its scope.
   * This models the condition for 'Dead Store Elimination' optimization.
   */
  predicate hasNoReadUntilScopeExit() {
    // We check if there is any Access node in the CFG reachable from this call
    // that reads the same memory object, within the same scope.
    
    // Get the memory object targeted by the memset
    MemoryLocation memLoc = getTargetExpr().asA<MemoryLocation>();
    if memLoc = null then
      // Fallback: try to resolve to a variable directly if it's a simple var
      exists(VariableAccess va | va = getTargetExpr().asA<VariableAccess>() | 
        memLoc = va.getVariable().getLocation()
      )
    endif;

    if memLoc = null then result = false else
      // Check for any Read Access in the CFG successors up to scope exit
      // We use a simplified reachability check: 
      // If there is a path from this Call to an ExitNode containing a Read of memLoc
      
      // Note: Full CFG analysis is complex. We approximate by checking
      // if the variable is used as an r-value (read) in the same block or subsequent blocks
      // before the function returns or the variable goes out of scope.
      
      // A robust way in CodeQL is to check if the value flows to a Read.
      // Here we assume if the pointer is not used to read, it's safe to flag.
      
      // We look for any Access node 'a' such that:
      // 1. 'a' is a read (isRead())
      // 2. 'a' accesses 'memLoc'
      // 3. 'a' is reachable from 'this' in the CFG
      // 4. 'a' is in the same scope (approximated by same function/block context)
      
      // To avoid overfitting, we check if the target variable itself is ever read.
      exists(Variable v | v = getTargetVar() | 
        not exists(Access acc | 
          acc.isRead() and 
          acc.getExpr().getValue().equals(v) and 
          // Reachability check: acc is after this call
          this.getCFGNode().canReach(acc.getCFGNode())
        )
      )
    endif;
  }

  /**
   * Helper to get the underlying variable if possible.
   */
  Variable getTargetVar() {
    result = getTargetExpr().asA<VariableAccess>().getVariable()
  }
}
