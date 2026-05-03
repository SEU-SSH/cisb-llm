/**
 * @name Compiler-Introduced Race Condition via Unprotected Memory Cache
 * @description Detects patterns where a local variable caches a shared memory field
 *              without a memory barrier, allowing compiler optimization to introduce
 *              a race condition during concurrent access.
 * @kind problem
 * @problem.severity warning
 * @precision high
 * @id cpp/cisb-unprotected-memory-cache
 * @tags security, correctness, concurrency, compiler
 */

import cpp
import DataFlow
import CISBUnprotectedCache

from RootCauseUnit rcu, Expr cachedVar, Expr usage
where environmentUnit(rcu, cachedVar, usage)
select rcu, cachedVar, usage, "Potential CISB: Unprotected shared memory cache may be optimized away, causing race condition."
