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
import query

from ControlFlowUnit write, RootCauseUnit asmStmt
where write.dominates(asmStmt) and environment_unit()
select write, asmStmt, "Inline assembly '{asmStmt}' lacks a 'memory' clobber while accepting pointer inputs. " +
                   "Preceding memory write at '{write}' may be eliminated or reordered by the compiler, " +
                   "potentially compromising security-sensitive operations."
