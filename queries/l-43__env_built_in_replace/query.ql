/**
 * @name Compiler-Introduced Security Bug: Loop-to-Memset Optimization on Device Memory
 * @description Detects loops writing consecutive values to memory that compilers may optimize into bulk operations like memset. On architectures enforcing strict I/O access rules, this can cause crashes or security violations.
 * @kind problem
 * @problem.severity warning
 * @precision high
 * @id cpp/cisb-loop-to-memset-device-memory
 * @tags security, external/cwe/cwe-755, cisb
 */

import cpp
import query

from BulkMemOpt::RootCauseUnit loop, ExprStmt stmt, AssignmentExpr assign
where
  BulkMemOpt::controlFlowUnit(loop, stmt) and
  assign = stmt.getExpr() and
  BulkMemOpt::environmentUnit(assign.getLValue())
select loop, "Compiler may optimize this sequential write loop into a bulk memory operation (e.g., memset). If targeting device/I/O memory, this violates architecture-specific access rules and may cause crashes."
