/**
 * @name GCC 4.8/4.9 Union Initialization Optimization Bug
 * @description Detects union initialization patterns that may trigger incorrect
 *              compiler optimizations in GCC 4.8/4.9, resulting in zeroed fields.
 * @kind problem
 * @problem.severity warning
 * @precision high
 * @id cpp/gcc-union-init-bug
 * @tags security, correctness, compiler-introduced
 */
import cpp
import GCCUnionInitOptimization

from UnionCrossMemberInit expr1, UnionCrossMemberInit expr2
where
  expr1.accessesDifferentMemberPath(expr2) and
  inSequentialInitScope(expr1, expr2) and
  assumesGCC48_49OptimizationEnv()
select expr1, expr2, "Potential GCC 4.8/4.9 union initialization optimization bug: cross-member initialization detected."
