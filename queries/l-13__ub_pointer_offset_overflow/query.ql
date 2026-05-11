import cpp
import query

from VulnerableMemberCheck vcheck
where isInLoopCondition(vcheck)
select vcheck, "Vulnerable loop condition: Clang may optimize away NULL check on member address &ptr->field if field offset > 0."
