/**
 * @name Compiler-Introduced Security Bug: Redundant Elimination of Non-Volatile Inline Assembly
 * @description Detects repeated non-volatile inline assembly calls with identical templates 
 *              within a function, where compiler optimization may incorrectly eliminate the second call.
 * @kind problem
 * @problem.severity warning
 * @precision high
 * @id cpp/cisb/redundant-non-volatile-asm
 */

import cpp
import CISB_InlineAsm_Removal

from NonVolatileAsm a1, NonVolatileAsm a2
where rootCauseUnit(a1, a2) and controlFlowUnit(a1, a2) and environmentUnit()
select a2, a2, "Potential CISB: Second non-volatile inline assembly call may be eliminated by compiler optimization despite hidden hardware state changes."
