import cpp
import CISB_MemsetReturnReg

/**
 * @name Compiler-Introduced Register Corruption via Memset Return Contract Violation
 * @description Detects functions that violate the implicit ABI contract of returning their first argument,
 *              leading to register corruption under GCC optimizations.
 * @kind problem
 * @problem.severity error
 * @precision high
 */
from root_cause_unit func, Parameter firstArg
where environment_unit() and control_flow_unit(func, firstArg)
select func, firstArg, "Potential CISB: Function may violate return-register contract under optimization."
