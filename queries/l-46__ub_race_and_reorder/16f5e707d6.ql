/**
 * @name Compiler Store Tearing on Tagged Pointer Assignment
 * @description Detects assignments to shared struct fields where tagged pointer computations
 *              lack atomic semantics, allowing compiler store tearing under concurrent access.
 * @kind problem
 * @problem.severity warning
 * @precision high
 * @tags security, correctness, concurrency, compiler
 */
import cpp
import cisb_store_tearing

from AssignExpr e
where root_cause_unit(e) and control_flow_unit(e) and environment_unit(e)
select e, "Compiler may tear this tagged pointer assignment to $@. Use WRITE_ONCE() or atomic primitives."
