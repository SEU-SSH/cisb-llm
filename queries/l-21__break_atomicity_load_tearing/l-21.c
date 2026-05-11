#include <pthread.h>
#include <stdatomic.h>
#include <stdint.h>
#include <stdio.h>
#include <time.h>
#include <unistd.h>

/* Kernel-like one-copy access helpers for a 64-bit PTE value. */
#define WRITE_ONCE(x, v) (*(volatile __typeof__(x) *)&(x) = (v))
#define READ_ONCE(x) (*(volatile __typeof__(x) *)&(x))

typedef uint64_t pte_t;

static atomic_int stop_flag;
static pte_t shared_pte;

/*
 * Vulnerable path: simulate compiler splitting one logical PTE update
 * into multiple stores, creating an observable intermediate value.
 */
static inline void vulnerable_set_pte(pte_t *ptep, pte_t new_pte)
{
	uint32_t *half = (uint32_t *)ptep;
	struct timespec ts = {0, 1000};

	half[0] = 0;                    /* transient non-present PTE */
	nanosleep(&ts, NULL);           /* widen the race window */
	half[1] = (uint32_t)(new_pte >> 32);
	half[0] = (uint32_t)new_pte;
}

/* Fixed path from the upstream commit idea: one-copy visible store. */
static inline void fixed_set_pte(pte_t *ptep, pte_t new_pte)
{
	WRITE_ONCE(*ptep, new_pte);
}

static void *reader_thread(void *arg)
{
	atomic_int *seen_transient_nonpresent = (atomic_int *)arg;

	while (!atomic_load_explicit(&stop_flag, memory_order_relaxed)) {
		pte_t cur = READ_ONCE(shared_pte);
		if ((cur & 1ULL) == 0) {
			atomic_store_explicit(seen_transient_nonpresent, 1, memory_order_relaxed);
			break;
		}
	}
	return NULL;
}

static int run_case(int use_fixed)
{
	pthread_t th;
	atomic_int seen;
	int i;

	/* present bit (bit0) is 1 in both old/new stable entries */
	pte_t old_pte = 0x1111111100000001ULL;
	pte_t new_pte = 0x2222222200000001ULL;

	atomic_store_explicit(&seen, 0, memory_order_relaxed);
	atomic_store_explicit(&stop_flag, 0, memory_order_relaxed);
	shared_pte = old_pte;

	if (pthread_create(&th, NULL, reader_thread, &seen) != 0) {
		return -1;
	}

	for (i = 0; i < 2000000 && !atomic_load_explicit(&seen, memory_order_relaxed); i++) {
		if (use_fixed) {
			fixed_set_pte(&shared_pte, new_pte);
			fixed_set_pte(&shared_pte, old_pte);
		} else {
			vulnerable_set_pte(&shared_pte, new_pte);
			vulnerable_set_pte(&shared_pte, old_pte);
		}
	}

	atomic_store_explicit(&stop_flag, 1, memory_order_relaxed);
	pthread_join(th, NULL);
	return atomic_load_explicit(&seen, memory_order_relaxed);
}

int main(void)
{
	int vuln_seen = run_case(0);
	int fixed_seen = run_case(1);

	if (vuln_seen < 0 || fixed_seen < 0) {
		puts("thread create failed");
		return 1;
	}

	printf("vulnerable path saw transient non-present PTE: %s\n",
		   vuln_seen ? "YES" : "NO");
	printf("fixed path (WRITE_ONCE) saw transient non-present PTE: %s\n",
		   fixed_seen ? "YES" : "NO");

	return 0;
}
