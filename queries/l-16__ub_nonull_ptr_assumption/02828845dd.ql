import cpp
import gcc_inline_asm_null_check

from InlineAsmStmt asmStmt, Variable var, IfStmt ifStmt
where controlFlowUnit(asmStmt, var, ifStmt)
select ifStmt, "CISB: Null check potentially eliminated by GCC -fdelete-null-pointer-checks due to inline asm dereference."
