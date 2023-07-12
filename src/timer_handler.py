#!/usr/bin/env python3
#
# Copyright (c) IBM Corp. 2023. All Rights Reserved.
# Project name: VPC File Storage Mount Helper
# This project is licensed under the MIT License, see LICENSE file in the root directory.


from common import *
from datetime import timedelta


class TimerHandler(SystemCtl):
    TIMER_FILE = '/etc/systemd/system/mount_helper.timer'
    SERVICE_FILE = '/etc/systemd/system/mount_helper.service'

    TIMER_CONFIG = """[Unit]
Description=Mount helper timer
[Timer]
Unit=mount_helper.service
OnCalendar=%s
[Install]
WantedBy=timers.target
"""

    SERVICE_CONFIG = """[Unit]
Description=Mount helper service
Wants=mount_helper.timer
[Service]
ExecStart=%s
Type=oneshot
[Install]
WantedBy=multi-user.target
"""

    def __init__(self):
        super().__init__('mount_helper.timer')

    def schedule_certs_renewal(self, date, command_path, min_future_secs=10):
        # schedule date must be in the future
        min_date = get_utc_now(seconds=min_future_secs)
        if date < min_date:
            self.LogInfo("Forcing schedule time to future: " + str(min_date))
            date = min_date

        show_tz = self.systemd_supports_utc()
        onCalendar = utc_format(date, show_tz)

        self.LogDebug("Setting Timer: " + onCalendar)
        data = TimerHandler.TIMER_CONFIG % onCalendar
        self.WriteFile(TimerHandler.TIMER_FILE, data, chmod=0o744)

        data = TimerHandler.SERVICE_CONFIG % (command_path)
        self.WriteFile(TimerHandler.SERVICE_FILE, data, chmod=0o744)
        return self.restart()

    def teardown(self):
        if self.FileExists(TimerHandler.TIMER_FILE):
            self.disable()
        self.RemoveFile(TimerHandler.TIMER_FILE)
        self.RemoveFile(TimerHandler.SERVICE_FILE)
