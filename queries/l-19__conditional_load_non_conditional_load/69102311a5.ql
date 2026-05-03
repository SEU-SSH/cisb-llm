/**
 * @name GCC Optimizer Conditional Store Bypass
 * @description Detects conditional stores to shared memory objects where the condition depends on synchronization state.
 *              This pattern is susceptible to compiler optimizations (e.g., GCC -O2 allow-store-data-races) that remove
 *              the conditional guard, leading to data races and inconsistent shared state.
 * @kind problem
 * @problem.severity warning
 * @precision high
 * @tags security, external/cwe/cwe-362, compiler-optimization
 */
import cpp
import VulnerableCISBPattern

from Expr store, Expr cond, Variable syncVar
where VulnerableCISBPattern::isVulnerableConditionalSharedStore(store, cond, syncVar)
select store, cond, syncVar, "Conditional store to shared memory guarded by sync variable '$@'. Susceptible to compiler optimization removing the guard."
