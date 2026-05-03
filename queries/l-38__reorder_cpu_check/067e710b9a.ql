import cpp
import <cisb_missing_memory_clobber>.qll

/**
 * @name Missing Memory Clobber in Conditionally Guarded Inline Assembly
 * @description Detects inline assembly blocks that lack a 'memory' clobber constraint 
 *              while being syntactically guarded by a runtime condition. Compiler optimizations 
 *              may reorder such assembly, bypassing the guard and causing hardware aborts.
 * @problem Security
 * @kind problem
 * @tags security, external/cwe/cwe-754, compiler-introduced
 */

from UnsafeInlineAsm asm
where isSyntacticallyGuarded(asm) and targetsHardwareWithConditionalSupport(asm)
select asm, "Unsafe inline assembly without 'memory' clobber. May be reordered across runtime guards, causing undefined behavior on specific hardware."
