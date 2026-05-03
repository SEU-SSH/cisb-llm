/**
 * @name Unaligned Struct Access via Compiler Alignment Assumption
 * @description Detects memory accesses to structs lacking explicit alignment attributes,
 *              where compiler optimizations assume natural alignment, potentially causing
 *              unaligned access faults on strict-alignment architectures.
 * @kind problem
 * @problem.severity warning
 * @precision high
 * @id cpp/unaligned-struct-access-cisb
 * @tags security, external/cwe-119, cisb
 */
import cpp
import UnalignedAccessCISB

from RootCauseUnit typeDef,
     Expr accessSite,
     Expr ptrSource
where
  accessSite.getType() = typeDef and
  ControlFlowUnit(ptrSource, accessSite) and
  EnvironmentUnit(accessSite)
select accessSite, "Unaligned memory access detected: compiler assumes natural alignment for struct '{0}', but pointer may be misaligned.", typeDef.getName()
