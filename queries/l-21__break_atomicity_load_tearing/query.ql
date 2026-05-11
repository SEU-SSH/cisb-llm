import cpp
import query

from RootCauseUnit rcu
where controlFlowUnit(rcu) and environmentUnit(rcu)
select rcu, "Vulnerable assignment to shared/hardware memory without atomic protection"
