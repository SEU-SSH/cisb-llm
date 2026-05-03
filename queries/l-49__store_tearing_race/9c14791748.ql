/**
 * @name CISB: Stale Read of Shared Variable without Synchronization
 * @description Detects direct reads of shared variables without synchronization wrappers
 *              that flow to sinks, potentially causing stale data exposure due to compiler optimizations.
 * @problem-severity high
 * @precision medium
 */
import cpp
import CISBStaleRead

from root_cause_unit src, Expr sink
where control_flow_unit(src, sink)
and environment_unit(src)
select src, "Unsynchronized read of shared variable flowing to sink", sink
