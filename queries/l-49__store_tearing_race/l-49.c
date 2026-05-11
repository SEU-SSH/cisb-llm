/*
 * 漏洞用例：缺少 READ_ONCE() 导致重复读取时得到过时值
 *
 * 对应 commit 9c14791748708d87c4d02ba74eb7e281e141d6e4
 * 原始代码在 debugfs 输出 pages_state_hold_cnt 时没有使用 READ_ONCE，
 * 编译器可能将多次读取提升/合并，导致显示的值与实际内存不一致。
 *
 * 编译：gcc -O2 -pthread -o read_once_bug read_once_bug.c
 * 运行：./read_once_bug
 */

#include <stdio.h>
#include <stdlib.h>
#include <pthread.h>
#include <unistd.h>
#include <stdint.h>

/* 模拟 pages_state_hold_cnt，被写线程不断递增 */
static volatile int keep_running = 1;
static uint32_t g_counter = 0;

/* 写线程：持续递增全局计数器 */
static void *writer(void *arg)
{
	while (__atomic_load_n(&keep_running, __ATOMIC_RELAXED))
		g_counter++;  /* 非原子自增，但只演示读取问题 */
	return NULL;
}

/* 读线程：模拟 debugfs 输出函数，连续两次读取 g_counter */
static void *reader(void *arg)
{
	/*
	 * 模拟 hns3_dump_page_pool_info() 中的两次读取：
	 * 第一次存到局部变量 v1，执行一些纯局部计算（模拟 sprintf 调用），
	 * 第二次再读取 v2。
	 * 由于局部计算没有副作用，编译器可能把两次读取合并为一次。
	 */
	uint32_t v1 = g_counter;

	/* 纯局部计算，不会修改 g_counter，编译器可安全优化 */
	uint32_t sum = 0;
	for (uint32_t i = 0; i < 1000000; i++)
		sum += i;

	uint32_t v2 = g_counter;

	printf("v1 = %u\n", v1);
	printf("v2 = %u\n", v2);
	printf("sum = %u (ignored)\n", sum);

	if (v1 == v2) {
		printf("BUG: v1 == v2! Compiler merged both reads, "
		       "showing stale value.\n");
	} else {
		printf("OK: values differ (compiler re-read from memory).\n");
	}

	/* 停止写线程 */
	__atomic_store_n(&keep_running, 0, __ATOMIC_RELAXED);
	return NULL;
}

int main(void)
{
	pthread_t wt, rt;

	pthread_create(&wt, NULL, writer, NULL);
	/* 给写线程一点时间递增 */
	usleep(1000);
	pthread_create(&rt, NULL, reader, NULL);

	pthread_join(rt, NULL);
	pthread_join(wt, NULL);

	return 0;
}