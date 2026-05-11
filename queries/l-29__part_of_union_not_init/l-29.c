/**
 * l-29.c
 * Source: GCC Bugzilla Bug 93270
 * 
 * Test case that demonstrates how compilers may optimize entire union zeroing
 * operations before assignment. long double types may have padding bits that
 * are not cleared by simply assigning 0.0 to the long double member, leading
 * to uninitialized memory usage if the union is used in a context that reads
 * those padding bits.
 * 
 * Evidence: When compiled with optimizations, the compiler may optimize the memset
 * of the entire union, leaving padding bits uninitialized.
 * 
 * Requirement: from GCC 4.8.0, -O1 and above.
 * Mitigation: use explicit_bzero to ensure all bits are cleared.
 */

#include <string.h>
#include <linux/string.h> // for explicit_bzero

typedef union { long double value; unsigned int word[4]; } memory_long_double;
static unsigned int ored_words[4];

__attribute__((noinline))
static void add_to_ored_words (long double x) {
    memory_long_double m;
    size_t i;
    memset (&m, 0, sizeof (m));
    // explicit_bzero(&m, sizeof(m));
    m.value = x;
    for (i = 0; i < 4; i++) {
        ored_words[i] |= m.word[i];
    }
}

int main() {
    long double dummy;
    add_to_ored_words(dummy);
    return 0;
}