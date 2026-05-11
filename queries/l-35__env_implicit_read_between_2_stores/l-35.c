/*
 * 漏洞用例：内联汇编缺少 "memory" clobber 导致失效存储被消除
 *
 * 模拟 commit 51bcf092917b 修复的问题：
 *   ip_fast_csum 的内联汇编从 iph 指向的内存读取数据，但未声明
 *   "memory" clobber。编译器因此可能认为前面的 iph->check = 0
 *   是死存储并将其消除，导致校验和基于旧值计算而出错。
 *
 * 编译：gcc -O2 -Wall -o ip_csum_bug ip_csum_bug.c
 * 运行：./ip_csum_bug
 * 预期输出 “BUG: checksum incorrect” 证明漏洞被触发。
 */

#include <stdio.h>

/* 有漏洞的 ip_fast_csum 实现 */
static inline unsigned short ip_fast_csum_bug(void *iph, unsigned int ihl)
{
	unsigned int sum;  /* 使用 32 位暂存，避免操作数大小问题 */

	/* 
	 * 内联汇编从 iph 指向的内存读取一个 16 位值（校验和字段）。
	 * "r"(iph) 让编译器认为只用到了寄存器的值，实际执行时却解引用该指针。
	 * 由于缺少 "memory" clobber，编译器不知内存被读取。
	 */
	__asm__ (
		"movzwl (%1), %0"    /* %0 = zero-extend( *(%1) ) */
		: "=r" (sum)
		: "r" (iph)
		/* 漏洞：此处没有 "memory" clobber */
	);
	return (unsigned short)sum;
}

int main(void)
{
	/* 模拟 IP 头：check 字段 + 数据 */
	struct {
		unsigned short check;
		unsigned short data;
	} iph;

	/* 初始值 */
	iph.check = 0x1234;
	iph.data  = 0x5678;

	/* 第一步：将校验和字段清零，准备计算校验和 */
	iph.check = 0;

	/*
	 * 第二步：调用有漏洞的 ip_fast_csum。
	 * 如果没有 "memory" clobber，编译器可能消除前面的 iph.check = 0
	 * 因为表面上看内联汇编没有读取该内存区域。
	 */
	unsigned short csum = ip_fast_csum_bug(&iph, 0);

	printf("Computed checksum: 0x%04X\n", csum);
	printf("Expected checksum: 0x%04X\n", 0x0000);

	if (csum != 0) {
		printf("\nBUG: checksum incorrect! "
		       "The store 'iph.check = 0' was eliminated by the compiler.\n");
		return 1;
	} else {
		printf("\nOK: store not eliminated "
		       "(try different optimization levels or GCC version).\n");
		return 0;
	}
}