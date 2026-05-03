import cpp
import ../cisb_member_address.qll

from VulnerableMemberCheck vcheck
where isInLoopCondition(vcheck)
select vcheck, "Vulnerable loop condition: Clang may optimize away NULL check on member address &ptr->field if field offset > 0."
