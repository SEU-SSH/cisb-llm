import cpp
import cisb_const_optimization

from Expr writeTarget, ConstEnvironmentVar cv
where rootCauseUnit(writeTarget, cv) and controlFlowUnit(writeTarget)
select writeTarget, cv, "Modification of const-qualified variable via pointer cast detected"
