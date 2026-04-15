# CISB Definition and Constraints

## What is CISB?

Compiler-Introduced Security Bugs (CISB) are security vulnerabilities that arise when compiler optimizations change the semantics of source code in ways that introduce security flaws. The term was coined by Xu et al. through manual investigation of compiler-introduced vulnerability reports from platforms like GCC Bugzilla and the Linux kernel.

The core theoretical insight is that **semantic equivalence of code does not ensure security**. Code processed by a compiler, especially after optimization, may produce serious security problems — there is a gap between semantic correctness and security.

## CISB Constraints

We define a software bug as a CISB when:  
- the code, when executed without optimization, has no security issues on the target machine; 
- compiler optimizations modify the code during compilation, creating the vulnerability; 
- the code should not contain any incorrect usage of language keywords; 
- the compiler optimization is formally correct, i.e., the compiler does not violate any language specification.

It is worth noting that the term “introduced” in CISB is only used to describe that the bug is created during the compilation phase, but is not present in the source code. The term is not supposed to assign responsibility.

## CISB Causal Logic

CISB often exists as a **hidden semantic conflict** between developer expectations and compiler assumptions. The trigger usually results from specific compiler processing within a given software/hardware environment that introduces security risks. The conflict manifests when:

- The developer writes code with a particular intent (e.g., clearing sensitive data, performing checks)
- The compiler makes assumptions about the code (e.g., "this store is dead", "this check is redundant because the condition involves undefined behavior")
- The compiler transforms the code based on these assumptions, removing or altering the security-critical operations, introducing other insecure logics
- The resulting binary is vulnerable in ways the source code was not

## Three-Facet Interaction

CISBs are classified using three dimensions:

1. **Developer Expectation**: The original intent or code pattern the developer expected to remain intact after compilation.
2. **Compiler Assumption and Behavior**: The specific assumptions the compiler makes about the code and the resulting "destructive processing" it performs (optimization passes, default behaviors).
3. **Environment and Security Consequence**: The specific software/hardware environment (including compiler options and runtime conditions) and the subsequent security impact triggered.

## CISB Security Implications

**Direct security implications**: endless loop/program hang, crash, memory corruption.  
**Indirect security implications**: data leak, control flow diversion, check removed/bypassed, side channel, speculative execution vulnerabilities.

## CISB Three-Layer Taxonomy

Based on existing research, major root causes of CISB include:

- **Implicit Specification (IS)**: The compiler makes assumptions that conflict with the functionality of the code in respect to the security property. This allows the compiler to perform aggressive optimizations to dismantle the security property. 
- **Orthogonal Specification (OS)**: The security property exceeds the semantic functionality scope of language specifications. They are orthogonal to those of correctness. Such security properties can be the execution time or the lifetime/region of sensitive data.

From Root Cause to Insecure optimization behaviors and Security consequences, listed as increasing levels:
- IS
    - Eliminating security related code
        - Elimination of security checks
        - Elimination of critical memory operations
    - Reordering order-sensitive security code
        - Disorder between order-sensitive memory operations
        - Disorder between security checks and dangerous operations
    - Introducing insecure instructions
        - Introduction of invalid instructions of certain environments
        - Introduction of insecure logic
- OS
    - Making sensitive data out of bound
        - Violation of sensitive data’s living-time boundary
        - Violation of sensitive data’s space(memory) boundary
    - Breaking timing guarantees
        - Introduction of the time side channel
        - Disordered concurrency sequence due to modification of duration
    - Introducing micro-architectural side effects
        - Introduction of bounds check bypass vulnerability