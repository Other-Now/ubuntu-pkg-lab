/* SPDX-License-Identifier: GPL-2.0 */
/*
 * Compatibility with kernels older than the one nano_blk was written for.
 *
 * Linux 6.9 (commit 27e32cd23fed, "block: pass a queue_limits argument to
 * blk_mq_alloc_disk") made blk_mq_alloc_disk() take the queue limits up front.
 * Ubuntu 24.04's GA kernel is 6.8, where it takes (set, queuedata) and limits
 * are applied afterwards with the blk_queue_*() setters.
 */
#ifndef NANO_BLK_COMPAT_H
#define NANO_BLK_COMPAT_H

#include <linux/version.h>
#include <linux/blk-mq.h>
#include <linux/blkdev.h>

static inline struct gendisk *
nblk_alloc_disk(struct blk_mq_tag_set *set, struct queue_limits *lim, void *data)
{
#if LINUX_VERSION_CODE >= KERNEL_VERSION(6, 9, 0)
	return blk_mq_alloc_disk(set, lim, data);
#else
	struct gendisk *disk = blk_mq_alloc_disk(set, data);
	struct request_queue *q;

	if (IS_ERR(disk))
		return disk;
	q = disk->queue;
	blk_queue_logical_block_size(q, lim->logical_block_size);
	blk_queue_physical_block_size(q, lim->physical_block_size);
	blk_queue_max_hw_sectors(q, lim->max_hw_sectors);
	blk_queue_max_discard_sectors(q, lim->max_hw_discard_sectors);
	blk_queue_max_write_zeroes_sectors(q, lim->max_write_zeroes_sectors);
	q->limits.discard_granularity = lim->discard_granularity;
	return disk;
#endif
}

#endif
