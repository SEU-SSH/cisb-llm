/*
 * 漏洞用例：store tearing on page->mapping
 * 
 * 模拟内核 mm/rmap.c 中 __page_set_anon_rmap() 因普通赋值可能
 * 被编译器拆分为多次写，导致无锁读者看到中间状态。
 *
 * 写者:
 *   mapping = anon_vma;          // 第一次写入（无标志）
 *   延迟（模拟撕裂间隙）
 *   mapping = anon_vma | FLAG;   // 第二次写入（加上 ANON 标志）
 *   然后设置 LRU 标志。
 *
 * 读者:
 *   若 LRU 标志已置位，读取 mapping，若为非 NULL 且缺少 FLAG，
 *   则触发 WARN/BUG。
 *
 * 编译: gcc -O2 -pthread -o mapping_tearing mapping_tearing.c
 */

#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <pthread.h>
#include <unistd.h>
#include <stdint.h>

#define PAGE_MAPPING_ANON  0x1UL          /* 模拟标志位 */

/* 模拟 page 结构体中的关键字段 */
struct page {
    void *mapping;
    unsigned long flags;
};

#define PG_lru  0x4UL                     /* 简化：LRU 标志位 */

static struct page test_page;
static volatile int running = 1;

/*
 * 写者线程：模拟 __page_set_anon_rmap 可能发生的撕裂写入。
 * 先将 mapping 赋值为纯地址（无标志），延迟后再或上标志位，
 * 最后设置 LRU 标志，模拟编译器可能的重排/撕裂行为。
 */
static void *writer_thread(void *arg)
{
    void *anon_vma = (void *)0xdeadbeef000UL;   /* 模拟 anon_vma 指针 */
    void *mapping_with_flag = (void *)((uintptr_t)anon_vma | PAGE_MAPPING_ANON);

    while (running) {
        /* Step 1: 仅写入地址部分（缺少标志位） */
        test_page.mapping = anon_vma;
        /* 短暂延迟，模拟撕裂间隙，增加读者命中中间状态的概率 */
        usleep(1);
        /* Step 2: 写入完整的 mapping（地址 + 标志） */
        test_page.mapping = mapping_with_flag;

        /* 设置 LRU 标志（模拟 SetPageLRU） */
        __sync_synchronize();           /* 确保 mapping 可见 */
        test_page.flags |= PG_lru;

        /* 重置状态，进行下一次迭代 */
        usleep(10);
        test_page.flags &= ~PG_lru;
        test_page.mapping = NULL;
    }
    return NULL;
}

/*
 * 读者线程：模拟 page_idle_clear_pte_refs 的无锁扫描。
 * 一旦检测到 LRU 标志，立即读取 mapping，并验证是否带有
 * PAGE_MAPPING_ANON 标志；否则触发漏洞。
 */
static void *reader_thread(void *arg)
{
    int count = 0;
    while (running) {
        /* 无锁检查 LRU 标志 */
        if (test_page.flags & PG_lru) {
            void *m = test_page.mapping;
            /* 内存屏障保证读取顺序（真实代码中也有屏障） */
            __sync_synchronize();

            /*
             * 如果 mapping 非 NULL 且缺少 PAGE_MAPPING_ANON 标志，
             * 则检测到中间状态，触发漏洞。
             */
            if (m != NULL && !((uintptr_t)m & PAGE_MAPPING_ANON)) {
                printf("BUG: observed torn mapping without ANON flag: %p\n",
                       m);
                printf("This would be mistaken for address_space, leading to crash.\n");
                running = 0;
                exit(1);
            }
            count++;
        }
    }
    printf("Reader checked %d times without issue (unlikely to reach here)\n", count);
    return NULL;
}

int main(void)
{
    pthread_t writer, reader;

    test_page.mapping = NULL;
    test_page.flags = 0;

    printf("Starting race simulation (press Ctrl-C to abort)...\n");
    pthread_create(&writer, NULL, writer_thread, NULL);
    pthread_create(&reader, NULL, reader_thread, NULL);

    /* 运行一段时间，等待漏洞触发 */
    sleep(5);
    running = 0;

    pthread_join(writer, NULL);
    pthread_join(reader, NULL);

    printf("Test finished without detecting torn mapping (unlikely)\n");
    return 0;
}