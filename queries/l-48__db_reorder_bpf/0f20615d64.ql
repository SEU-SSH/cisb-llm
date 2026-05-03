/**
 * @name CISB: Switch Fall-Through with Unprotected Address Calculation
 * @description Detects switch statements with missing case terminators that allow implicit fall-through. 
 *              Combined with unprotected address calculations and memory accesses, aggressive compiler 
 *              optimizations may duplicate or reorder these calculations across fall-through paths, 
 *              leading to mismatched memory access sizes and potential information disclosure.
 * @kind problem
 * @problem.severity warning
 * @precision medium
 * @id cpp/cisb-switch-fallthrough
 * @tags security, cisb, switch-fallthrough, compiler-optimization
 */

import cpp
import CISBSwitchFallThrough

from CISBSwitchFallThrough vsw
select vsw, "Switch statement with fall-through cases and unprotected address calculations detected. " +
          "Missing break statements allow implicit fall-through, which may cause the compiler to " +
          "duplicate or reorder address calculations across case arms, leading to mismatched memory access sizes."
