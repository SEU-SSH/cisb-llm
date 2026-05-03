/**
 * @name GCC Inline Assembly Missing Memory Clobber CISB
 * @description Detects inline assembly blocks lacking a 'memory' clobber that permit
 *              the compiler to eliminate or reorder preceding memory writes, potentially
 *              breaking security-critical operations like checksum updates or sensitive data clearing.
 * @kind problem
 * @problem.severity warning
 * @precision high
 * @id cpp/gcc-inline-asm-missing-memory-clobber
 * @tags security, external/cwe/cwe-676, cisb, compiler-introduced
 */

import cpp
import gcc_inline_asm_missing_memory_clobber.qll

from control_flow_unit write, root_cause_unit asm
where write.dominates(asm) and environment_unit()
select write, asm, "Inline assembly '{asm}' lacks a 'memory' clobber while accepting pointer inputs. " +
                   "Preceding memory write at '{write}' may be eliminated or reordered by the compiler, " +
                   "potentially compromising security-sensitive operations."
