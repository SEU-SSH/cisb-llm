/**
 * @name GCC Jump Table Retpoline Bypass (Spectre v2)
 * @description Detects switch statements likely compiled with jump tables, 
 *              which bypass retpoline mitigations and introduce Spectre v2 risks.
 * @kind problem
 * @problem.severity warning
 * @precision high
 * @tags security, cisb, spectre-v2, compiler-bug
 */

import cpp
import JumpTableRetpoline

from SwitchStmt s, SwitchJumpTableTrigger t
where t = s and triggersIndirectJumpDispatch(s)
      and lacksJumpTableMitigation()
      and isRetpolineSensitiveContext()
select s, "Switch statement with >20 cases likely uses a jump table, bypassing retpoline mitigations and introducing Spectre v2 risk."
