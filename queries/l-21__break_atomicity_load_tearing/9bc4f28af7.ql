import cpp
import CISB_AtomicWriteProtection

from RootCauseUnit rcu
where controlFlowUnit(rcu) and environmentUnit(rcu)
select rcu, "Vulnerable assignment to shared/hardware memory without atomic protection"
