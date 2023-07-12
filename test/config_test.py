# Copyright (c) IBM Corp. 2023. All Rights Reserved.
# Project name: VPC File Storage Mount Helper
# This project is licensed under the MIT License, see LICENSE file in the root directory.

from unittest.mock import MagicMock
from unittest import mock
import unittest
import os
import time
import config
from  common import *
from test_common import *


MY_STRONGSWAN_CONFIG = """
connections {
  <CONNECTION_NAME> {
    children {
        remote_ts = <REMOTE_IP>[tcp/2049]
    }
    remote_addrs = <REMOTE_IP>
    local {
        certs = <CLIENT_CERT_FILE>
    }
    remote {
      id = %any
    }
   }
}
"""
def make_test_filename(name):
    return make_filename(test_folder.name, name)


def make_cfg_file_name(ip):
    return make_test_filename("type_ibmshare_" + ip + ".conf")


def create_file(ip=None):
    if not ip:
        ip = random_ip()

    fpath = make_cfg_file_name(ip)
    with open(fpath, "w") as fp:
        fp.write("Any data")
    return fpath


def read_file(fpath):
    with open(fpath, "r") as fp:
        return fp.read()


def ss_setup(mins=0):
    test_folder.recreate()
    ss = config.StrongSwanConfig()
    SysApp.set_code(None)
    ss.SetDebugEnabled()
    ss.CLEANUP_FILE_MIN_AGE_MINS = mins
    ss.flatten_paths(test_folder.name)
    ss.get_config_template_text = MagicMock()
    ss.get_config_template_text.return_value = MY_STRONGSWAN_CONFIG
    return ss, []


class TestConfigOther(unittest.TestCase):

    def test_cleanup_unused_configs_file_not_removed(self):
        ip = random_ip()
        ss, mounts = ss_setup()
        my_file = create_file(ip)
        mounts.append(NfsMount(ip, "/path1", "here"))
        ss.cleanup_unused_configs(mounts)
        self.assertTrue(os.path.exists(my_file))

    def test_cleanup_unused_configs_file_removed(self):
        ss, mounts = ss_setup()
        my_file = create_file()
        ss.cleanup_unused_configs(mounts)
        self.assertFalse(os.path.exists(my_file))

    def test_cleanup_unused_configs_recent_file_not_removed(self):
        ss, mounts = ss_setup(5)
        my_file = create_file()
        ss.cleanup_unused_configs(mounts)
        self.assertTrue(os.path.exists(my_file))

    '''
    def test_cleanup_unused_configs_not_recent_file_removed(self):
        my_file = create_file()
        ss,mounts = ss_setup(1)
        print("Sleep 2 minutes")
        #time.sleep(122)  # wait over two minutes
        ss.cleanup_unused_configs(mounts)
        self.assertFalse(os.path.exists(my_file))
    '''

    def test_create_cfg(self):
        ss, _ = ss_setup()
        ip = random_ip()
        ss.create_config(ip)
        my_file = make_cfg_file_name(ip)
        self.assertTrue(os.path.exists(my_file))

        exp = MY_STRONGSWAN_CONFIG
        exp = exp.replace("<REMOTE_IP>", ip)
        exp = exp.replace("<CONNECTION_NAME>",
                          "ibmshare-ipsec-to-" + ip.replace(".", "-"))
        exp = exp.replace("<CLIENT_CERT_FILE>", ss.cert_filename())

        txt = read_file(my_file)
        self.assertEqual(remove_comments(txt), exp)

    def test_create_cfg_already_exists(self):
        ss, _ = ss_setup()
        ip = random_ip()
        ss.create_config(ip)
        my_file = make_cfg_file_name(ip)
        self.assertTrue(os.path.exists(my_file))

        st_old = os.stat(my_file)
        time.sleep(10)  # wait 10 seconds
        ss.SetDebugEnabled()
        ss.EnableLogStore()
        ss.create_config(ip)
        self.assertTrue(ss.HasLogMessage("Config data unchanged"))
        st_new = os.stat(my_file)
        self.assertNotEqual(st_old.st_mtime, st_new.st_mtime)

    def test_reload_certs_error(self):
        with MySubProcess(-99, ""):
            ss, _ = ss_setup(True)
            ss.is_reload = True
            ret = ss.reload_certs()
            self.assertFalse(ret)
            self.assertTrue(ss.is_reload)
            self.assertTrue(SysApp.is_code(SysApp.ERR_IPSEC_CFG))

    def test_reload_certs_ok(self):
        with MySubProcess(0, ""):
            ss, _ = ss_setup()
            ss.is_reload = True
            ret = ss.reload_certs()
            self.assertTrue(ret)
            self.assertFalse(ss.is_reload)
            self.assertTrue(SysApp.is_none())

    def test_reload_config_error(self):
        with MySubProcess(-99, ""):
            ss, _ = ss_setup(True)
            ss.is_reload = True
            ret = ss.reload_config()
            self.assertFalse(ret)
            self.assertTrue(ss.is_reload)
            self.assertTrue(SysApp.is_code(SysApp.ERR_IPSEC_CFG))


    def test_reload_config_ok(self):
        with MySubProcess(0, ""):
            ss, _ = ss_setup()
            ss.is_reload = True
            ret = ss.reload_config()
            self.assertTrue(ret)
            self.assertFalse(ss.is_reload)
            self.assertTrue(SysApp.is_none())

    def test_ipsec_msg_config_ok(self):
        def ok(val):
            self.assertFalse(is_empty(val))

        def is_func(func):
            func()  # just check it can be called

        for o in [config.StrongSwanConfig()]:
            ok(o.NAME)
            ok(o.VERSION_TAG)
            ok(o.EXE_PATH)
            ok(o.INT_CA_PATH)
            ok(o.ROOT_CA_PATH)
            ok(o.KEY_FILE_PATH)
            ok(o.CERT_PATH)
            ok(o.IPSEC_CONFIG_PATH)
            ok(o.IPSEC_CONFIG_TEXT)
            is_func(o.set_version)
            is_func(o.reload_config)
            is_func(o.reload_certs)


if __name__ == '__main__':
    unittest.main()
    test_cleanup()
