/**
 * l-38.c
 * Source: Linux Commit b407460ee99033503993ac7437d593451fcdfe44
 * 
 * Test case that demonstrates how loop invariant code motion can lead to
 * a busy-wait loop that never relaxes, causing potential CPU hangs.
 * 
 * Evidence: When compiled with optimizations, the compiler consider the var assignment
 * const at compile time, may hoist the load out of the loop.
 * 
 * Reuqirement: GCC/Clang -O1 or higher, only -S not linked.
 * Mitigation: Insert a compiler barrier inside the loop after the load to prevent code motion.
 */

extern int global_var;

int poll_without_relax() {
    int val;
    for (;;) {
        val = global_var;  // Load that can be hoisted by optimizer
        // barrier();      // Prevent code motion
        if (val != 0) break;
    }
    return val;
}