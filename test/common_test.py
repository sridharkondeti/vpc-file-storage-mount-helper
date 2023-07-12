# Copyright (c) IBM Corp. 2023. All Rights Reserved.
# Project name: VPC File Storage Mount Helper
# This project is licensed under the MIT License, see LICENSE file in the root directory.

from unittest.mock import MagicMock
from unittest import mock
import unittest
from io import StringIO
from test_common import *
from common import *


class TestCommonCode(unittest.TestCase):

    def test_util_funcs(self):
        self.assertEqual(trim(" ddd "), "ddd")
        self.assertTrue(is_empty("  "))
        self.assertTrue(is_empty(None))
        self.assertEqual(to_int(" 123 "), 123)
        self.assertEqual(to_int("  "), 0)

    def test_log_to_file(self):
        tst = MountHelperLogger()
        tst.SetLogToFileEnabled()
        log = tst.LOG_FILE
        tst.LogError("this is error")
        tst.LogInfo("this is info")
        tst.LogDebug("this is debug")

        self.assertTrue(file_contains(log, "this is error"))
        self.assertTrue(file_contains(log, "this is info"))
        self.assertFalse(file_contains(log, "this is debug"))
        if os.path.exists(tst.LOG_FILE):
            os.remove(tst.LOG_FILE)

    def test_subprocess_run(self):
        cmd = ["ls", "/tmp"]
        proc = SubProcess(cmd)
        out = proc.run()
        self.assertEqual(out.returncode, 0)

    def test_subprocess_run_stream(self):
        cmd = ["ls", "/tmp"]
        proc = SubProcess(cmd)
        out = proc.stream()
        self.assertEqual(out.returncode, 0)

    def test_exteract_version(self):

        version = extract_version("245 (245.4-4ubuntu3.17)")
        self.assertEqual("245", version)

        version = extract_version(" (2.3.)2")
        self.assertEqual("2.3", version)

        version = extract_version(" (2.3.5aa")
        self.assertEqual("2.3.5", version)

        version = extract_version(" (2.1 3.5aa")
        self.assertEqual("2.1", version)

        version = extract_version(" (aaa.fdsfdsfdsfs")
        self.assertIsNone(version)


if __name__ == '__main__':
    unittest.main()
