import cpp
import MemClearOptimization

from MemClearCall m
where m.isLocalVariableTarget() and m.hasNoReadUntilScopeExit()
select m, "Potential CISB: memset() on local variable may be optimized away as dead code. Use memzero_explicit() or ensure the variable is read afterwards.""
