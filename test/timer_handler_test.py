# Copyright (c) IBM Corp. 2023. All Rights Reserved.
# Project name: VPC File Storage Mount Helper
# This project is licensed under the MIT License, see LICENSE file in the root directory.

from datetime import datetime, timedelta
from config import get_utc_now, get_utc_date
import os
import timer_handler
import unittest
from common  import *
from test_common import *


class TestTimerHandler(unittest.TestCase):

    def test_schedule_not_in_future(self):
        tho = timer_handler.TimerHandler()
        tho.EnableLogStore()
        tho.SetDebugEnabled()
        ret = tho.schedule_certs_renewal(get_utc_now(), "ls")
        self.assertTrue(ret)
        self.assertTrue(tho.HasLogMessage("Forcing schedule time to future:"))

    def test_schedule_certs_renewal_job_ran_ok(self):
        touch = test_folder.get_temp_filename("touch.txt")
        tho = timer_handler.TimerHandler()
        out = tho.teardown()
        tho.SetDebugEnabled()
        when = get_utc_now() + timedelta(seconds=11)
        ret = tho.schedule_certs_renewal(when, "touch " + touch)
        self.assertTrue(ret)

        sleep_msg(4, "active")
        self.assertTrue(tho.is_active())

        # wait 1 minute till file exists
        secs = 0
        while secs <= 60:
            if os.path.exists(touch):
                break
            sleep_msg(10, "for file: " + touch)
            secs += 10

        self.assertTrue(os.path.exists(touch))

        out = tho.teardown()
        remove_file(touch)


if __name__ == "__main__":
    unittest.main()
