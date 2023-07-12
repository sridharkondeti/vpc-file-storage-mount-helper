# Copyright (c) IBM Corp. 2023. All Rights Reserved.
# Project name: VPC File Storage Mount Helper
# This project is licensed under the MIT License, see LICENSE file in the root directory.

from args_handler import ArgsHandler
import sys
import unittest

ARGV = ['/sbin/mount.ibmshare', '-o', 'rw,args1,arg2=test2,arg3=test3',
        '192.168.1.1:/path1', '/my_mount1']
CMD = ['mount', '-t', 'nfs4', '-o', 'sec=sys,nfsvers=4.1,rw,args1,arg2=test2,arg3=test3',
       '192.168.1.1:/path1', '/my_mount1']
ESSENTIAL_OPTIONS = 'sec=sys,nfsvers=4.1'


def get_args(secure, extra=None):
    args = ARGV.copy()
    if secure:
        args[2] += ",secure=true"
    else:
        args[2] += ",secure=false"
    if extra:
        args.append(extra)
    return args


class TestArgsHandler(unittest.TestCase):

    def test_mount_invalid_args(self):
        sys.argv = ["these", "are", "invalid", "args"]
        ao = ArgsHandler()
        out = ao.parse()
        self.assertFalse(out)

    def test_get_mount_source(self):
        sys.argv = ARGV
        ao = ArgsHandler()
        ao.parse()
        expected = ARGV[3]
        self.assertEqual(expected, ao.mount_source)

    def test_get_mount_point(self):
        sys.argv = ARGV
        ao = ArgsHandler()
        ao.parse()
        expected = ARGV[4]
        self.assertEqual(expected, ao.mount_point)

    def test_get_mount_path(self):
        sys.argv = ARGV
        ao = ArgsHandler()
        ao.parse()
        expected = ARGV[3].split(':')[1]
        self.assertEqual(expected, ao.mount_path)

    def test_get_mount_host(self):
        sys.argv = ARGV
        ao = ArgsHandler()
        ao.parse()
        expected = ARGV[3].split(':')[0]
        self.assertEqual(expected, ao.ip_address)

    def test_get_mount_options(self):
        sys.argv = ARGV
        ao = ArgsHandler()
        ao.parse()
        expected = ARGV[2]
        self.assertEqual(expected, ao.options)

    def test_get_mount_cmd_line(self):
        sys.argv = ARGV
        ao = ArgsHandler()
        ao.parse()
        out = ao.get_mount_cmd_line()
        expected = CMD
        self.assertEqual(expected, out)

    def test_has_secure_true(self):
        sys.argv = get_args(True)
        ao = ArgsHandler()
        ao.parse()
        self.assertTrue(ao.is_secure)
        self.assertEqual(ARGV[2], ao.options)

    def test_has_secure_false(self):
        sys.argv = get_args(False)
        ao = ArgsHandler()
        ao.parse()
        self.assertFalse(ao.is_secure)
        self.assertEqual(ARGV[2], ao.options)

    def test_parse_invalid_src(self):
        sys.argv = ['app', 'src', '/my_mount1']
        ao = ArgsHandler()
        out = ao.parse()
        self.assertFalse(out)

    def test_parse_invalid_dest(self):
        sys.argv = ['app', 'src:aaa', '']
        ao = ArgsHandler()
        out = ao.parse()
        self.assertFalse(out)

    def test_parse_ok(self):
        sys.argv = ARGV
        ao = ArgsHandler()
        out = ao.parse()
        self.assertTrue(out)

    def test_is_debug_is_enabled(self):
        sys.argv = get_args(True, "-v")
        print(sys.argv)
        out = ArgsHandler.is_debug_enabled()
        self.assertTrue(out)

    def test_is_debug_not_enabled(self):
        sys.argv = ARGV
        out = ArgsHandler.is_debug_enabled()
        self.assertFalse(out)

    def test_is_debug_is_passed_to_mount(self):
        sys.argv = get_args(True, "-v")
        ao = ArgsHandler()
        ao.parse()
        cmd = ao.get_mount_cmd_line()
        self.assertTrue("-v" in cmd)

    def test_get_renew_certificate_cmd_line(self):
        ao = ArgsHandler()
        cmd = ao.get_renew_certificate_cmd_line()
        self.assertTrue(len(cmd) > 0)


if __name__ == '__main__':
    unittest.main()
