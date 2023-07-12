# Copyright (c) IBM Corp. 2023. All Rights Reserved.
# Project name: VPC File Storage Mount Helper
# This project is licensed under the MIT License, see LICENSE file in the root directory.

import file_lock
import unittest
import time
import threading
import random

BLOCK_LOCK_FILE = '/tmp/ibm_mount_helper_block.lck'
NON_BLOCK_LOCK_FILE = '/tmp/ibm_mount_helper_non_block.lck'


class TestLockHandler(unittest.TestCase):

    def test_grab_non_blocking_lock(self):
        lh = file_lock.LockHandler(NON_BLOCK_LOCK_FILE)
        out = lh.grab_non_blocking_lock()
        self.assertTrue(out)
        # check that lock is already acquired
        lh2 = file_lock.LockHandler(NON_BLOCK_LOCK_FILE)
        out = lh2.grab_non_blocking_lock()
        self.assertFalse(out)
        lh.release_lock()

    def test_release_non_blocking_lock(self):
        lh = file_lock.LockHandler(NON_BLOCK_LOCK_FILE)
        out = lh.grab_non_blocking_lock()
        self.assertTrue(out)
        lh.release_lock()
        # check that lock is already acquired
        lh2 = file_lock.LockHandler(NON_BLOCK_LOCK_FILE)
        out = lh2.grab_non_blocking_lock()
        self.assertTrue(out)
        lh2.release_lock()

    def test_release_blocking_lock(self):
        lh = file_lock.LockHandler(BLOCK_LOCK_FILE)
        out = lh.grab_blocking_lock()
        self.assertTrue(out)
        lh.release_lock()
        # check lock released
        lh2 = file_lock.LockHandler(BLOCK_LOCK_FILE)
        out = lh2.grab_blocking_lock()
        self.assertTrue(out)
        lh2.release_lock()

    def test_is_locked_blocking(self):
        lh = file_lock.LockHandler(BLOCK_LOCK_FILE)
        self.assertTrue(lh.grab_blocking_lock())
        lh2 = file_lock.LockHandler(BLOCK_LOCK_FILE)
        self.assertTrue(lh2.is_locked())
        lh.release_lock()
        self.assertFalse(lh2.is_locked())

    def test_is_locked_NON_blocking(self):
        lh = file_lock.LockHandler(NON_BLOCK_LOCK_FILE)
        self.assertTrue(lh.grab_non_blocking_lock())
        lh2 = file_lock.LockHandler(NON_BLOCK_LOCK_FILE)
        self.assertTrue(lh2.is_locked())
        lh.release_lock()
        self.assertFalse(lh2.is_locked())

    def test_blocking_lock(self):
        completed = []

        def thread_func(name):
            lh = file_lock.LockHandler(BLOCK_LOCK_FILE)
            print("Wating for Lock: " + name)
            out = lh.grab_blocking_lock()
            self.assertTrue(out)
            secs = random.randint(1, 5)
            print("Lock got:sleep (%d) seconds" % secs, name)
            time.sleep(secs)
            completed.append(name)
            lh.release_lock()

        threads = []
        for x in range(10):
            name = "thread-%d" % x
            thread = threading.Thread(target=thread_func, args=[name])
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        assert len(completed) == 10


if __name__ == '__main__':
    unittest.main()
