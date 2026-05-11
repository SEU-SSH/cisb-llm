/*
 * 漏洞用例：ftrace_event_call 对齐不一致导致错误的数组遍历
 *
 * 原始漏洞：GCC 4.5 将未显式对齐的结构体默认对齐到最大可能值（32 字节）。
 * 当 ftrace_event_call 与其他 4 字节对齐的对象混合存放在特殊 section 中时，
 * 对象之间可能插入填充，但遍历代码使用固定的 sizeof(struct) 作为步长，
 * 就会错误地将填充区域视为有效的 ftrace_event_call，随后调用其中的垃圾函数指针。
 *
 * 本用例模拟此场景：两个 ftrace_event_call 对象 ev1（对齐 4）和 ev2（对齐 32）
 * 通过 __attribute__((section(".my_array"))) 放入同一段，遍历该段时会出现
 * 多余的元素，其内容为未初始化的填充字节，对其 func 的调用将导致段错误。
 *
 * 编译：gcc -Wall -o ftrace_align_bug ftrace_align_bug.c
 * 运行：./ftrace_align_bug （预期崩溃）
 */

#include <stdio.h>
#include <stdint.h>
#include <stddef.h>

/* 简化的 ftrace_event_call 结构 */
struct ftrace_event_call {
    void (*func)(void);
    int data;
};

/* 声明自定义段的起止符号（由链接器自动生成） */
extern struct ftrace_event_call __start_my_array[];
extern struct ftrace_event_call __stop_my_array[];

/* 两个事件对象，放入同一段，但不同对齐 */
__attribute__((section(".my_array"), aligned(4)))
struct ftrace_event_call ev1 = {
    .func = (void (*)(void))0xdead0001,    /* 用于演示的非法地址 */
    .data = 0x1111
};

__attribute__((section(".my_array"), aligned(32)))
struct ftrace_event_call ev2 = {
    .func = (void (*)(void))0xdead0002,
    .data = 0x2222
};

/* 真实的有效函数，用于对比 */
void valid_func(void) {
    printf("  Executed valid_func()\n");
}

int main(void) {
    char *start = (char *)__start_my_array;
    char *end   = (char *)__stop_my_array;
    unsigned long section_size = end - start;
    unsigned long elem_size = sizeof(struct ftrace_event_call);
    unsigned long count = section_size / elem_size;

    printf("=== ftrace_event_call alignment bug simulation ===\n");
    printf("Section size: %lu bytes\n", section_size);
    printf("Element size: %lu bytes\n", elem_size);
    printf("Calculated element count: %lu (expected 2)\n\n", count);

    printf("Addresses:\n");
    printf("  __start_my_array = %p\n", start);
    printf("  __stop_my_array  = %p\n", end);
    printf("  &ev1 = %p\n", &ev1);
    printf("  &ev2 = %p\n", &ev2);
    printf("  Gap between ev1 and ev2: %ld bytes\n\n",
           (char*)&ev2 - (char*)&ev1 - elem_size);

    printf("Traversing the array with fixed stride:\n");

    for (unsigned long i = 0; i < count; i++) {
        struct ftrace_event_call *call =
            (struct ftrace_event_call *)(start + i * elem_size);
        printf("  Element %lu at %p: func=%p, data=0x%x\n",
               i, call, call->func, call->data);

        /* 尝试调用 func —— 若读取到有效地址会执行，不然通常崩溃 */
        if (call->func) {
            printf("    -> Calling func()...\n");
            call->func();   /* BUG: 若为填充数据，此处崩溃 */
        } else {
            printf("    -> func is NULL, skipping\n");
        }
    }

    printf("Traversal finished (unexpected)\n");
    return 0;
}