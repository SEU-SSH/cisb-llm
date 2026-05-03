/**
 * @name CISB: Compiler Optimization Removes Shift Sanity Check
 * @description Detects patterns where a compiler may optimize away a sanity check on a shift result because the shift amount is unchecked.
 * @kind problem
 * @problem.severity warning
 * @precision high
 * @id cpp/cisb-shift-check-removal
 * @tags security, cisb, optimization, undefined-behavior
 */

import cpp
import CISBShiftLibrary

from CISBShiftCheckRemoval bug
select bug, "Potential CISB: Shift sanity check may be removed by compiler due to unchecked shift amount."
