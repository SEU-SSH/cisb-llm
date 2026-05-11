#include <stdint.h>
#include <string.h>
#include <stdio.h>

/* 模拟位提取宏：从 val 中获取 [high:low] 位 */
#define WIL_GET_BITS(val, high, low) \
    (((val) >> (low)) & ((1u << ((high) - (low) + 1)) - 1u))

/* 状态描述符就绪位在 d0 的第 31 位 */
#define RX_DESC_RDY_BIT_POS 31

/* 硬件状态消息结构（压缩格式） */
struct wil_rx_status_compressed {
    uint32_t d0;          /* 包含 desc_rdy bit 及其他控制信息 */
    uint32_t payload[2];  /* 模拟其他数据字段，硬件可能稍后才写入 */
};

/* 驱动维护的状态环 */
struct wil_status_ring {
    uint8_t *va;          /* 映射到硬件状态 FIFO 的基地址 */
    uint32_t elem_size;   /* 每条状态消息的大小 */
    uint32_t swhead;      /* 软件读取头指针 */
};

/*
 * 漏洞版本：直接 memcpy 整个状态消息，然后再提取 desc_rdy 位。
 * 编译器可能优化为先拷贝全部数据，最后才读取 desc_rdy 位，
 * 或者 CPU 乱序执行。在硬件并发更新数据时，先读取到的其他字段
 * 可能是无效的旧值。
 */
static inline void wil_get_next_rx_status_msg_v1(
    struct wil_status_ring *sring, void *msg)
{
    memcpy(msg, (void *)(sring->va + (sring->elem_size * sring->swhead)),
           sring->elem_size);
}

/* 从已拷贝的消息中提取 desc_rdy 位 */
static inline int wil_rx_status_get_desc_rdy_bit(void *msg)
{
    return WIL_GET_BITS(((struct wil_rx_status_compressed *)msg)->d0,
                        RX_DESC_RDY_BIT_POS, RX_DESC_RDY_BIT_POS);
}

/* 模拟硬件写入更新，同时返回是否设置了 desc_rdy */
static int hw_update_status(struct wil_rx_status_compressed *status,
                           int ready, uint32_t payload0, uint32_t payload1)
{
    /* 假设硬件先写 payload，最后才设置 desc_rdy 位 */
    status->payload[0] = payload0;
    status->payload[1] = payload1;
    /* memory barrier 保证 payload 写入晚于 desc_rdy 可见 */
    __sync_synchronize();
    if (ready)
        status->d0 = (1u << RX_DESC_RDY_BIT_POS);
    else
        status->d0 = 0;
    __sync_synchronize();
    return ready;
}

int main(void)
{
    struct wil_rx_status_compressed hw_status;
    memset(&hw_status, 0, sizeof(hw_status));

    struct wil_status_ring sring = {
        .va = (uint8_t *)&hw_status,
        .elem_size = sizeof(hw_status),
        .swhead = 0
    };

    /* 硬件准备一条有效数据，但 desc_rdy 仍为 0 */
    hw_update_status(&hw_status, 0, 0xDEADBEEF, 0xCAFEBABE);

    struct wil_rx_status_compressed local_msg;

    /*
     * 驱动读取状态消息：
     * 先全部 memcpy，然后检查 desc_rdy 位。
     * 由于没有防护，payload 字段可能来自硬件写入的中间状态，
     * 即 desc_rdy = 0 时硬件可能已经部分更新了 payload，
     * 导致驱动读到无效数据。
     */
    wil_get_next_rx_status_msg_v1(&sring, &local_msg);
    int dr_bit = wil_rx_status_get_desc_rdy_bit(&local_msg);

    printf("dr_bit: %d\n", dr_bit);
    printf("payload[0]: 0x%X\n", local_msg.payload[0]);
    printf("payload[1]: 0x%X\n", local_msg.payload[1]);

    if (dr_bit == 0 && (local_msg.payload[0] != 0 || local_msg.payload[1] != 0))
        printf("!! 竞态条件触发：payload 在 desc_rdy=0 时非零，数据无效！\n");
    else
        printf("未明显触发（实际环境中并发更新时仍可能发生）\n");

    return 0;
}