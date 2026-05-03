/**
 * @name Compiler-Optimized Timing Delay Loop
 * @description Detects loops used for timing delays that lack volatile qualifiers, making them susceptible to elimination by optimizing compilers.
 * @kind problem
 * @problem.severity warning
 * @precision high
 * @tags security, cisb, performance
 */
import cpp
import <cisb_empty_loop_timing_delay.qll>

from RootCauseUnit loop, ControlFlowUnit cf, EnvironmentUnit env
where cf = loop
select loop, "Potential compiler-optimized timing delay loop without volatile qualifier.", loop.getLocation(), "Consider adding 'volatile' to loop counters or using explicit delay APIs."
