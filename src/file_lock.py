#!/usr/bin/env python3
#
# Copyright (c) IBM Corp. 2023. All Rights Reserved.
# Project name: VPC File Storage Mount Helper
# This project is licensed under the MIT License, see LICENSE file in the root directory.


from common import *
import fcntl
import os


class LockHandler(MountHelperBase):

    @staticmethod
    def mount_share_lock():
        return LockHandler('/var/lock/ibm_mount_helper.lck')

    @staticmethod
    def renew_cert_lock():
        return LockHandler('/var/lock/ibm_mount_helper_renew.lck')

    def __init__(self, lock_file):
        self.lock_file = lock_file
        self.lock_fd = -1

    def grab_non_blocking_lock(self):
        return self._grab_lock(False)

    def grab_blocking_lock(self):
        return self._grab_lock(True)

    def _lock(self, blocking):
        open_mode = os.O_RDWR | os.O_CREAT | os.O_TRUNC
        self.lock_fd = os.open(self.lock_file, open_mode)
        # Exclusive lock
        if blocking:
            fcntl.flock(self.lock_fd, fcntl.LOCK_EX)
        else:
            fcntl.flock(self.lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)

        flags = fcntl.fcntl(self.lock_fd, fcntl.F_GETFD)
        fcntl.fcntl(self.lock_fd, fcntl.F_SETFD, flags)

    def _grab_lock(self, blocking):
        try:
            self._lock(blocking)
            self.LogDebug("Locked ok:" + self.lock_file)
            return True
        except IOError as e:
            self.LogError('The other mount command is in processing:' + str(e))
        except Exception as ex:
            self.LogException("GrabLock", ex)
        self.LogError("Failed to get lock")
        return False

    # check if file is already locked
    def is_locked(self):
        try:
            self._lock(False)
            self.release_lock()
            return False
        except Exception as ex:
            return True

    def release_lock(self):
        if self.lock_fd >= 0:
            fcntl.flock(self.lock_fd, fcntl.LOCK_UN)
            os.close(self.lock_fd)
            self.LogDebug("File unlocked:" + self.lock_file)
            self.lock_fd = -1
