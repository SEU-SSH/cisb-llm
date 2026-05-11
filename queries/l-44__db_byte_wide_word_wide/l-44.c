/*
 * 漏洞用例：编译器错误优化未对齐访问
 *
 * 模拟 commit 8c031ba63f8f 修复的场景：
 *   GCC 看到 extern 变量类型为 __le32，便假设其自然对齐，
 *   将 get_unaligned_le32() 中的逐字节读取优化为 4 字节加载，
 *   而该变量实际存放于未对齐地址，从而导致错误。
 *
 * 编译：gcc -O2 -Wall -o unaligned_bug unaligned_bug.c
 * 运行：./unaligned_bug
 * 预期输出“BUG: corrupted value …”证明漏洞触发。
 */

#include <stdint.h>
#include <stdio.h>

/* 模拟内核的 get_unaligned_le32 —— 逐字节小端读取 */
static inline __attribute__((always_inline))
uint32_t get_unaligned_le32(const void *p)
{
	const unsigned char *cp = (const unsigned char *)p;
	return (uint32_t)cp[0]       | ((uint32_t)cp[1] << 8) |
	       ((uint32_t)cp[2] << 16) | ((uint32_t)cp[3] << 24);
}

int main(void)
{
	/*
	 * 故意将 0xDEADBEEF 放在一个未对齐的地址上。
	 * buf[0] 是填充字节，从 buf+1 开始才是有效数据，该地址不是 4 的倍数。
	 */
	char buf[] = { 0x00, 0xEF, 0xBE, 0xAD, 0xDE };
	const void *unaligned = buf + 1;	/* 实际未对齐 */

	/*
	 * 这一行模拟了漏洞的根源：
	 * 编译器被告知可以认为 unaligned 指向一个 4 字节对齐的地址，
	 * 就像原始代码中看到 extern __le32 变量一样。
	 */
	const void *assumed_aligned = __builtin_assume_aligned(unaligned, 4);

	/* 调用“逐字节”读取函数 —— 却被编译器错误地优化为 *(uint32_t*)p */
	uint32_t value = get_unaligned_le32(assumed_aligned);

	printf("Read value : 0x%08X\n", value);
	printf("Expected   : 0x%08X\n", 0xDEADBEEF);

	if (value != 0xDEADBEEF) {
		printf("\nBUG: value corrupted! Compiler replaced byte-wise "
		       "access with a direct 4‑byte load from an unaligned address.\n");
		return 1;
	} else {
		printf("\nOK: compiler did not optimize away the byte-wise access "
		       "(try -O3 or a different GCC version).\n");
		return 0;
	}
}