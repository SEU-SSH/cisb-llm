#include <string.h>

#define MUTEX_DEBUG_INIT  0x11

struct waiter {
    int magic;
    void *list;
    int extra[2];
};

void debug_mutex_lock_common(struct waiter *waiter) {
    memset(waiter, MUTEX_DEBUG_INIT, sizeof(*waiter));
    waiter->magic = (int)waiter;  /* 依赖 memset 返回正确的 waiter 指针 */
}