#define _XOPEN_SOURCE 700
#include <pthread.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

struct vm_area_struct {
	unsigned long vm_start;
	unsigned long vm_end;
	struct vm_area_struct *next;
};

struct mm_struct {
	pthread_rwlock_t mmap_sem;
	struct vm_area_struct *mmap_cache;
	struct vm_area_struct *mmap;
};

/* Mirrors old kernel macro style used by the fix commit. */
#define ACCESS_ONCE(x) (*(volatile __typeof__(x) *)&(x))

/*
 * Vulnerable pattern: plain load from mmap_cache. Under read lock, multiple
 * reader threads can still update mmap_cache, so compiler re-fetch of this
 * value can observe another reader's write.
 */
static struct vm_area_struct *find_vma_buggy(struct mm_struct *mm,
											 unsigned long addr)
{
	struct vm_area_struct *vma;

	pthread_rwlock_rdlock(&mm->mmap_sem);

	/* Vulnerable line: equivalent to pre-fix kernel code. */
	vma = mm->mmap_cache;
	if (!(vma && vma->vm_end > addr && vma->vm_start <= addr)) {
		for (vma = mm->mmap; vma; vma = vma->next) {
			if (vma->vm_end > addr && vma->vm_start <= addr) {
				break;
			}
		}
		/* Same trigger condition as commit: readers update shared cache. */
		mm->mmap_cache = vma;
	}

	pthread_rwlock_unlock(&mm->mmap_sem);
	return vma;
}

/* Fixed form (kept for contrast): vma = ACCESS_ONCE(mm->mmap_cache); */
static struct vm_area_struct *find_vma_fixed(struct mm_struct *mm,
											 unsigned long addr)
{
	struct vm_area_struct *vma;

	pthread_rwlock_rdlock(&mm->mmap_sem);

	vma = ACCESS_ONCE(mm->mmap_cache);
	if (!(vma && vma->vm_end > addr && vma->vm_start <= addr)) {
		for (vma = mm->mmap; vma; vma = vma->next) {
			if (vma->vm_end > addr && vma->vm_start <= addr) {
				break;
			}
		}
		mm->mmap_cache = vma;
	}

	pthread_rwlock_unlock(&mm->mmap_sem);
	return vma;
}

struct worker_arg {
	struct mm_struct *mm;
	unsigned long base;
	int use_fixed;
};

static void *worker(void *arg)
{
	struct worker_arg *wa = (struct worker_arg *)arg;
	unsigned long sum = 0;

	for (int i = 0; i < 500000; i++) {
		unsigned long addr = wa->base + (unsigned long)(i & 0x7f);
		struct vm_area_struct *v = wa->use_fixed
									? find_vma_fixed(wa->mm, addr)
									: find_vma_buggy(wa->mm, addr);
		if (v) {
			sum += v->vm_start;
		}
	}

	return (void *)(uintptr_t)sum;
}

int main(void)
{
	struct mm_struct mm;
	struct vm_area_struct vma1 = {0x1000, 0x2000, NULL};
	struct vm_area_struct vma2 = {0x3000, 0x4000, NULL};
	pthread_t t1, t2;
	struct worker_arg a1, a2;

	vma1.next = &vma2;
	mm.mmap = &vma1;
	mm.mmap_cache = &vma1;
	pthread_rwlock_init(&mm.mmap_sem, NULL);

	/* Two reader threads call find_vma concurrently under read lock. */
	a1.mm = &mm;
	a1.base = 0x1800;
	a1.use_fixed = 0;
	a2.mm = &mm;
	a2.base = 0x3800;
	a2.use_fixed = 0;

	if (pthread_create(&t1, NULL, worker, &a1) != 0) {
		return 1;
	}
	if (pthread_create(&t2, NULL, worker, &a2) != 0) {
		return 1;
	}

	pthread_join(t1, NULL);
	pthread_join(t2, NULL);
	pthread_rwlock_destroy(&mm.mmap_sem);

	puts("done");
	return 0;
}
