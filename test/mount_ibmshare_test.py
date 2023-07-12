# Copyright (c) IBM Corp. 2023. All Rights Reserved.
# Project name: VPC File Storage Mount Helper
# This project is licensed under the MIT License, see LICENSE file in the root directory.

from unittest.mock import MagicMock
from unittest import mock
import mount_ibmshare
import common
import unittest
import sys
from test_common import *
from renew_certs import RenewCerts
from args_handler import ArgsHandler


def do_mount(ret=0, data=""):
    mo = mount_ibmshare.MountIbmshare()
    mo.is_share_mounted = MagicMock(return_value = False) 
    mo.SetDebugEnabled()
    mo.EnableLogStore()
    with MySubProcess(ret, data) as run:
        args = ArgsHandler.get_mount_args()
        out = mo.mount(args)
        mo._run = run  # temp store
    return mo, out


def init_ocert(ocert, load=True, ncw=True, exp=False, rcw=True,
               create_config=True, cleanup_config=True):
    ox = ocert.return_value
    ox.load_certificate.return_value = load
    ox.new_cert_now.return_value = ncw
    ox.is_certificate_eligible_for_renewal.return_value = exp
    ox.renew_cert_now.return_value = rcw
    ox.cert_filename.return_value = "path/my_cert_name"
    ipsec = MagicMock()
    ipsec.create_config = MagicMock(return_value=create_config)
    ipsec.cleanup_unused_configs = MagicMock(return_value=cleanup_config)
    ox.get_ipsec_mgr.return_value = ipsec
    ox.ipsec = ipsec
    return ox

def do_already_mounted(ret=0, data="",ip="",path=""):
    mo = mount_ibmshare.MountIbmshare()
    with MySubProcess(ret, data) as run:
        ret = mo.is_share_mounted(ip,path)
    return mo, ret


class TestMountIbmshareOther(unittest.TestCase):

    def test_load_mounted_shares_returns_one_mount(self):
        data = "1.1.1.1:mount_path unknown mounted_at ccc nfs"
        mo, ret = do_already_mounted(data=data)
        self.assertFalse(ret)
        self.assertEqual(len(mo.mounts), 1)
        mount = mo.mounts[0]
        self.assertTrue(mount.ip == "1.1.1.1")
        self.assertTrue(mount.mount_path == "mount_path")
        self.assertTrue(mount.mounted_at == "mounted_at")

    def test_load_mounted_shares_returns_error(self):
        mo, ret = do_already_mounted(ret=-99)
        self.assertTrue(ret)
        self.assertIsNone(mo.mounts)

    def test_is_share_mounted(self):
        data = "1.1.1.1:already_mounted unknown mounted_at ccc nfs"
        mo, ret = do_already_mounted(data=data,
            ip='1.1.1.1',path="already_mounted")
        self.assertTrue(ret)

    def test_share_not_mounted(self):
        mo, ret = do_already_mounted()
        self.assertFalse(ret)

    @mock.patch('sys.argv', ["invalid", "args"])
    def test_mount_invalid_args(self):
        mo = mount_ibmshare.MountIbmshare()
        ret = mo.run()
        self.assertFalse(ret)

    def test_non_secure_mounts_ok(self):
        ip = "192.168.56.1"
        with mock.patch.object(sys, "argv", ["app", ip + ":/testshare", "/media/test"]):
            ipsec = RenewCerts().get_ipsec_mgr()
            ipsec.create_config(ip)
            self.assertIsNotNone(ipsec.get_config(ip))
            _, ret = do_mount()
            self.assertIsNone(ipsec.get_config(ip))
            self.assertTrue(ret)
            self.assertTrue(ipsec.HasLogMessage("Non-IPsec mount requested"))


@mock.patch('sys.argv', ["app", "192.168.56.1:/testshare", "/media/test",  "-o secure=true"])
@mock.patch('mount_ibmshare.RenewCerts')
class TestMountIbmshare(unittest.TestCase):

    def test_mount_with_new_cert_got_ok(self, ocert):
        init_ocert(ocert, True, False, True, True)
        mo, ret = do_mount()
        self.assertTrue(ret)
        cmd = ['mount', '-t', 'nfs4', '-o', 'sec=sys,nfsvers=4.1,',
               '192.168.56.1:/testshare', '/media/test']
        self.assertEqual(mo._run.func.call_count, 1)
        #mo._run.func.assert_called_with(cmd)

    def test_load_mounted_shares_returns_error(self, ocert):
        _, ret = do_mount(-990, "")
        self.assertFalse(ret)

    def test_root_cert_not_installed(self, ocert):
        ocert.return_value.root_cert_installed.return_value = False
        mo, ret = do_mount()
        self.assertFalse(ret)
        self.assertTrue(mo.HasLogMessage("Root Certificate must be installed"))

    def test_renew_fails(self, ocert):
        init_ocert(ocert, True, False, True, False)
        _, ret = do_mount()
        self.assertFalse(ret)
        self.assertEqual(ocert.return_value.renew_cert_now.call_count, 1)

    def test_mount_cmd_fails(self, ocert):
        init_ocert(ocert, True, False, False, False)
        _, ret = do_mount(-99)
        self.assertFalse(ret)

    def test_strong_swan_config_create(self, ocert):
        o = init_ocert(ocert)
        _, ret = do_mount()
        self.assertTrue(ret)
        o.ipsec.create_config.assert_called_with(
            "192.168.56.1")

    def test_strong_swan_config_create_fails(self, ocert):
        o = init_ocert(ocert, create_config=False)
        _, ret = do_mount()
        self.assertFalse(ret)
        self.assertEqual(o.ipsec.create_config.call_count, 1)

    def test_strong_swan_config_cleanup(self, ocert):
        o = init_ocert(ocert, cleanup_config=False)
        _, ret = do_mount()
        self.assertTrue(ret)
        o.ipsec.cleanup_unused_configs.assert_called_with([])


if __name__ == '__main__':
    unittest.main()
