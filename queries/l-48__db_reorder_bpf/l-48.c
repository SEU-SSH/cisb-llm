/*
 * 漏洞用例：BPF_CORE_READ_BITFIELD() 缺失 break 导致 fall-through
 *
 * 原始问题: switch 中每个 case 都没有 break，导致无论字段大小如何，
 * 最终都会执行到 case 8，产生错误的 8 字节读取。后续 libbpf 严格
 * 校验时发现读取大小与原始字段大小不一致，从而报错。
 *
 * 编译: gcc -O2 -Wall -o bitfield_bug bitfield_bug.c
 * 运行: ./bitfield_bug
 */

#include <stdio.h>
#include <stdint.h>

/* 测试结构，包含一个 uint32_t 字段和一个相邻的 uint64_t 字段 */
struct test_data {
    uint32_t val1;          /* 我们只打算读取 4 字节 */
    uint64_t val2;          /* 如果 fall-through 会读到这部分数据 */
};

/* 漏洞版本：switch 无 break，导致 total_size 最终固定为 8 */
static inline unsigned long long read_field_bug(const void *p, int actual_size)
{
    unsigned long long val;
    int total_size = actual_size;   /* 记录期望大小，仅用于对比 */

    switch (actual_size) {
    case 1: val = *(const uint8_t  *)p;
    case 2: val = *(const uint16_t *)p;
    case 4: val = *(const uint32_t *)p;
    case 8: val = *(const uint64_t *)p;
    }

    /* 通常后续会进行位移和掩码操作，这里简单回显实际读取的值 */
    printf("  [BUG]  expected size=%d, read value=0x%llx\n", total_size,
           (unsigned long long)val);
    return val;
}

/* 正确版本：每个 case 有 break，读取大小与字段匹配 */
static inline unsigned long long read_field_fixed(const void *p, int actual_size)
{
    unsigned long long val;
    int total_size = actual_size;

    switch (actual_size) {
    case 1: val = *(const uint8_t  *)p; break;
    case 2: val = *(const uint16_t *)p; break;
    case 4: val = *(const uint32_t *)p; break;
    case 8: val = *(const uint64_t *)p; break;
    }

    printf("  [FIX]  expected size=%d, read value=0x%llx\n", total_size,
           (unsigned long long)val);
    return val;
}

int main(void)
{
    struct test_data data;
    data.val1 = 0xAABBCCDD;          /* 低位 4 字节 */
    data.val2 = 0x1122334455667788ULL; /* 相邻的 8 字节 */

    printf("Data layout:\n");
    printf("  val1 (offset 0) = 0x%X\n", data.val1);
    printf("  val2 (offset 4) = 0x%llX\n\n", (unsigned long long)data.val2);

    printf("Attempting to read val1 (uint32_t, size=4):\n");
    unsigned long long bug_value = read_field_bug(&data, 4);
    unsigned long long fix_value = read_field_fixed(&data, 4);

    printf("\n");

    /* 因为 fall-through，bug_value 实际是 8 字节内存中 val1 和 val2 的组合 */
    if (bug_value != (unsigned long long)data.val1) {
        printf("BUG confirmed! Fall-through caused 8-byte read.\n");
        printf("  Expected value: 0x%llX\n", (unsigned long long)data.val1);
        printf("  Actual value:   0x%llX\n", bug_value);
        printf("  High 32 bits are from adjacent val2 -> data corruption.\n");
    } else {
        printf("Bug not triggered (unlikely with missing break).\n");
    }

    return 0;
}