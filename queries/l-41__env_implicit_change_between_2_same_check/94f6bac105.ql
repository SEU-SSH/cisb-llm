import cpp
import CompilerOptimizationBug

from MissingMemoryClobberAsmFunc func, CallExpr call1, CallExpr call2
where hasConsecutiveCallsInSameScope(func, call1, call2) and assumesPureFromOptimizer(func)
select call1, call2, func, 
  "Potential CISB: Compiler may merge consecutive calls to inline asm function ('" + func.getName() + "') lacking memory clobber."
