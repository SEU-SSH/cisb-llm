/**
 * @name GCC-7 Unaligned External Variable Optimization
 * @description Detects external variable declarations with implicit alignment > 1 byte
 * that lack explicit alignment attributes. Compiler optimizations may transform byte-wise
 * accesses into word-wise accesses, causing unaligned access faults on strict-alignment
 * architectures like PARISC.
 * @kind problem
 * @problem.severity warning
 * @precision high
 * @tags security, external, optimization, alignment, cisb
 */
import cpp
import gcc7unalignedextvar

from RootCauseUnit var, ControlFlowUnit access
where EnvironmentUnit()
select access, var, "External variable '$@' declared with implicit alignment > 1 byte. \nCompiler may optimize accesses to word-wise, causing unaligned access faults on strict-alignment architectures."
