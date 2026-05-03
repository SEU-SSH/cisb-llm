/**
 * @name Uninitialized Struct Padding Leak to User Space
 * @description Detects cases where individual field assignments to a struct with implicit padding lead to uninitialized data exposure when copied to user space.
 * @kind problem
 * @problem.severity warning
 * @precision medium
 * @tags security, external/cwe/CWE-200, cisb, padding-leak
 */

import cpp
import StructPaddingLeak

from StructWithImplicitPadding structType,
     Expr structInst,
     Field f1, Field f2,
     Stmt assign1, Stmt assign2,
     Expr userBuf
where
  structType.hasPotentialPadding() and
  structType.getAField() = f1 and
  structType.getAField() = f2 and
  f1 != f2 and
  assignsFieldIndividually(structInst, f1, assign1) and
  assignsFieldIndividually(structInst, f2, assign2) and
  lacksAggregateInitialization(structInst) and
  copiesToUserSpace(structInst, userBuf)
select structInst, assign1,
  "Struct instance '{0}' assigned field-by-field without aggregate initialization. Implicit padding may leak uninitialized data to user space."
