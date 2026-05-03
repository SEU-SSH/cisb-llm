/**
 * @name IO Memory Wrapper Optimized memset/memcpy
 * @description Detects IO memory access wrappers that invoke standard memory functions (memset/memcpy).
 *              When compiled with optimizations, GCC may assume aligned memory and replace these calls
 *              with optimized sequences, causing hardware faults on devices that do not support unaligned accesses.
 * @problem Compiler-Introduced Security Bug: Optimization of standard memory APIs inside IO wrappers violates
 *          hardware alignment constraints.
 * @severity warning
 * @precision high
 */
import cpp
import io_mem_wrapper

from CallExpr call, Function caller, Function callee
where rootCauseUnit(call, caller, callee)
select call, caller, callee, "IO memory accessor '$caller' calls standard memory function '$callee'. Compiler may optimize this assuming alignment, violating IO memory constraints."
