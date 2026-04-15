# Concept Distinctions for CISB Analysis

## Overview

When analyzing whether a bug report reveals a Compiler-Introduced Security Bug (CISB), it is critical to distinguish between several related but distinct concepts. Misclassification — particularly confusing programming errors with CISBs — is the most common source of false positives in automated CISB detection.

## Key Concepts

### 1. Default Behavior

**Definition**: Default behaviors are actions that compilers decide are appropriate to perform based on language semantics or optimization conventions. These are not explicit developer requests but standard compiler operations.

**Examples**:
- **Inlining**: The compiler replaces a function call with the function body for performance.
- **Type Promotion**: Integer types smaller than `int` are promoted to `int` in expressions.
- **Assuming Function Must Return**: The compiler assumes all non-void functions return a value on every code path.
- **Register Allocation**: The compiler decides which variables to keep in registers vs. memory.
- **Instruction Reordering**: The compiler reorders instructions for pipeline efficiency while maintaining (apparent) sequential semantics.

**Relevance to CISB**: Default behaviors can be the mechanism through which a CISB manifests. If a default behavior causes a security-relevant semantic change, it may constitute a CISB. The question is whether the default behavior violated a reasonable developer expectation with security implications.

### 2. Programming Error

**Definition**: Programming errors are violations **explicitly marked as invalid** by the language specification. These include constraint violations, reserved keyword misuse, and other constructs that the language standard prohibits.

**Critical Rule: Programming errors are NOT CISBs.**

**Examples**:
- Using a reserved keyword as a variable name
- Violating type constraints explicitly stated in the standard
- Using syntax that the language grammar prohibits
- Accessing memory that is definitively out of bounds by the programmer's own explicit logic (e.g., using a negative array index in a context where it clearly represents a coding mistake)

**Why Programming Errors ≠ CISB**: If the code violates an explicit rule of the language specification, the resulting behavior is the programmer's fault, not the compiler's. The compiler is not introducing a bug — the bug was already present in the source code.

### 3. Undefined Behavior (UB)

**Definition**: Undefined Behavior is behavior for which the language standard **imposes no requirements**. So triggerring UB is not necessarily violating language specifications. 

**Critical Nuances**:
- **UB is NOT necessarily a programming error.** Do not assume that all UB cases indicate programming errors. UB exists on a spectrum.
- **UB that has security implications even without compiler processing may be a programming error** — for example, using a negative array index that corrupts memory regardless of optimization level.
- **UB that only causes security problems after compiler optimization may indicate a CISB** — for example, signed integer overflow that the developer handles safely at runtime but the compiler uses to eliminate a security check.
- **In kernel environments, some UB is intentional and required** — for example, data races in kernel code may be deliberate design choices, not programming errors.

**Examples of UB**:
- Signed integer overflow
- Dereferencing a null pointer
- Accessing an object through a pointer of incompatible type (strict aliasing violation)
- Shifting by an amount equal to or greater than the bit width
- Reading uninitialized memory

**Key Question**: When UB appears in a bug report, ask: "Does this UB have security implications even WITHOUT compiler optimization?" If yes → likely a programming error. If the security impact only appears AFTER the compiler exploits the UB for optimization → may be a CISB.

### 4. Environment Assumption

**Definition**: Environment assumptions are platform-specific, hardware-specific, or configuration-specific behaviors that affect how code executes. These are not part of the language standard but are properties of the execution environment.

**Examples**:
- Address alignment of the target architecture
- Size of pointers and integer types
- Available hardware features (e.g., AES-NI instructions)
- Operating system API behavior
- Specific compiler version behaviors

**Relevance to CISB**: If a bug report indicates that the issue is caused by external factors such as hardware, environment, or configuration — rather than compiler optimization — then it is **not** a CISB. Environment assumptions help distinguish between platform bugs and compiler-introduced bugs.
