/*
	x86-64 gcc 4.1.2-12.0.1 -O0
	x86-64 clang 3.0.0-14.0.0 -O0
	Compile and run the program, the padding 4 bytes in struct addr_sa and struct sockaddr_154 will not be initialized, thus leaked to user space.
*/

#include <stdint.h>
#include <string.h>
#include <stdio.h>

/* ---- simulate kernel data structure ---- */

#define ADDR_LEN 8

struct addr_sa {
    int      addr_type;   // 4
    uint16_t pan_id;      // 2

    union {
        uint8_t hwaddr[ADDR_LEN]; // 8
        uint16_t short_addr;      // 2
    } un;
    /* implicit padding: 2 bytes */
};

struct sockaddr_154 {
    uint16_t family;      // 2
    /* implicit padding: 2 bytes */
    struct addr_sa addr;  // 14 + pad2 = 16
};

/* simulate copy_to_user */
extern void opaque_copy(void *dst, const void *src, size_t n);

void recvmsg_like(uint8_t *user, int type) {
    struct sockaddr_154 sa;   // defined on stack

    /* only initialize data fields */

    sa.family = 0xF00D;

    sa.addr.addr_type = type;
    sa.addr.pan_id = 0x1234;

    if (type == 1) {
        sa.addr.un.short_addr = 0xABCD;
        /* hwaddr left */
    } else {
        for (int i = 0; i < ADDR_LEN; i++)
            sa.addr.un.hwaddr[i] = i;
        /* short_addr left */
    }

    /* struct copy, uninitialized padding leak */
    // printf("%ud", sizeof(struct addr_sa));  // 16 bytes
    opaque_copy(user, &sa, sizeof(sa));
}