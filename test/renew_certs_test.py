# Copyright (c) IBM Corp. 2023. All Rights Reserved.
# Project name: VPC File Storage Mount Helper
# This project is licensed under the MIT License, see LICENSE file in the root directory.

from unittest import mock
import unittest
from renew_certs import RenewCerts
from mount_ibmshare import MountIbmshare
from test_common import *
from common import *
from config_test import ss_setup


class CertFolders:
    def __init__(self, renew):
        self.dir = MyTempDir("2")
        self.name = self.dir.name
        self.renew = renew
        self.certs = []

    def write_root(self, *names):
        for name in names:
            self.dir.write_file(name, TEST_ROOT_CERT)
            self.certs.append(name)

    def certs_installed_count(self, cnt):
        ipsec = self.renew.get_ipsec_mgr()
        cas = ipsec.root_cert_filenames()
        return len(cas) == cnt

    def certs_installed_ok(self, certs=None):
        certs = certs if certs else self.certs
        ipsec = self.renew.get_ipsec_mgr()
        cas = ipsec.root_cert_filenames()
        self.dir.cleanup()
        if len(cas) != len(certs):
            return False
        files = ''.join(cas)
        for cert in certs:
            if cert not in files:
                return False
        return True


def create_config(datai, datac):
    dirc = MyTempDir("/config")
    diri = MyTempDir("/install")

    namec = make_filename(dirc.name, "share.conf")
    remove_file(namec)
    namei = make_filename(diri.name, "share.conf")
    remove_file(namei)

    ShareConfig.conf_path = dirc.name
    if datai is not None:
        RenewCerts().WriteFile(namei, datai, mkdir=False)
    if datac is not None:
        RenewCerts().WriteFile(namec, datac, mkdir=True)
    return diri, dirc


def setup_config(datai, datac=None):
    renew = setup_renew()
    diri, dirc = create_config(datai, datac)
    dir = CertFolders(renew)
    return renew, dir, diri


def setup_renew(av=True, gt=True, sr=True, gc=True, nxt=True):
    ss, _ = ss_setup(10)
    renew = RenewCerts()
    ss.write_new_certs = MagicMock(return_value=True)
    renew.get_ipsec_mgr = MagicMock(return_value=ss)
    renew.EnableLogStore()
    renew.SetDebugEnabled()
    renew.is_metadata_service_available = MagicMock(return_value=av)
    renew.get_token = MagicMock(return_value=gt)
    renew.new_certificate_signing_request = MagicMock(return_value=sr)
    renew.generate_certs = MagicMock(return_value=gc)
    renew.schedule_next_renewal = MagicMock(return_value=nxt)
    return renew


def setup_cmd_line(ren):
    renew = setup_renew()
    renew.SetLogToFileEnabled()
    renew.metadata_renew_cert = MagicMock(return_value=ren)
    return renew


class TestRenewCerts(unittest.TestCase):
    def test_renew_cert_get_token_fails(self):
        renew = setup_renew(gt=False)
        self.assertFalse(renew.metadata_renew_cert())
        self.assertTrue(SysApp.is_code(SysApp.ERR_METADATA_TOKEN))

    def test_metadata_unavailable(self):
        renew = setup_renew(av=False)
        self.assertFalse(renew.metadata_renew_cert())
        self.assertTrue(SysApp.is_code(SysApp.ERR_METADATA_UNAVAILABLE))

    def test_renew_cert_use_old_key(self):
        renew = setup_renew()
        renew.private_key = None
        ipsec = renew.get_ipsec_mgr()
        write_file(ipsec.private_key_filename(), TEST_PRIVATE_KEY)
        self.assertTrue(renew.metadata_renew_cert())
        self.assertEqual(TEST_PRIVATE_KEY, renew.private_key)

    def test_renew_cert_use_new_key(self):
        renew = setup_renew()
        renew.get_ipsec_mgr().read_private_key = MagicMock(return_value=None)
        renew.set_private_key = MagicMock()
        renew.new_private_key = MagicMock(return_value=True)
        self.assertTrue(renew.metadata_renew_cert())
        self.assertEqual(renew.new_private_key.call_count, 1)
        self.assertEqual(renew.set_private_key.call_count, 0)

    def test_renew_cert_generate_fails(self):
        renew = setup_renew(gc=False)
        self.assertFalse(renew.metadata_renew_cert())
        self.assertTrue(SysApp.is_code(SysApp.ERR_METADATA_CERT_RENEW))

    def test_renew_cert_generate_ok(self):
        renew = setup_renew()
        self.assertTrue(renew.metadata_renew_cert())
        self.assertTrue(SysApp.is_none())

    def test_renew_cert_cmd_line_no_mounts(self):
        renew = setup_cmd_line(True)
        renew.get_ipsec_mgr().cleanup_unused_configs = MagicMock(return_value=False)
        self.assertTrue(renew.renew_cert_cmd_line())
        self.assertEqual(renew.metadata_renew_cert.call_count, 0)

    def test_renew_cert_cmd_line_mount_locked(self):
        renew = setup_cmd_line(True)
        mount = MountIbmshare()
        mount.lock()
        renew.renew_cert_cmd_line()
        mount.unlock()
        self.assertEqual(renew.metadata_renew_cert.call_count, 1)

    def test_renew_cert_cmd_line_ok(self):
        renew = setup_cmd_line(True)
        renew.get_ipsec_mgr().cleanup_unused_configs = MagicMock(return_value=True)
        renew.get_ipsec_mgr().create_config("1.1.1.1")
        renew.renew_cert_cmd_line()
        self.assertEqual(renew.metadata_renew_cert.call_count, 1)

    def test_python_exception_thrown(self):
        renew = setup_cmd_line(True)
        renew.get_ipsec_mgr().cleanup_unused_configs = MagicMock(
            side_effect=Exception("Test"))
        self.assertFalse(renew.renew_cert_cmd_line())
        self.assertTrue(SysApp.is_code(SysApp.ERR_PYTHON_EXCEPTION))

    def test_renew_cert_cmd_line_10_retries(self):
        renew = setup_cmd_line(False)
        renew.RENEW_RETRY_DELAY = 1
        renew.RENEW_MAX_RETRIES = 10
        renew.get_ipsec_mgr().cleanup_unused_configs = MagicMock(return_value=True)
        renew.get_ipsec_mgr().create_config("1.1.1.1")
        ret = renew.renew_cert_cmd_line()
        self.assertFalse(ret)
        self.assertEqual(renew.metadata_renew_cert.call_count, 10)
        self.assertTrue(renew.HasLogMessage("Renew cert failed, retry(10)"))

    def test_install_root_cert_using_config_no_config_file(self):
        renew, cert, inst = setup_config(None)
        ret = renew.install_root_cert_using_config(inst.name, cert.name)
        self.assertFalse(ret)
        self.assertTrue(renew.HasLogMessage("Missing configuration file:"))

    def test_install_root_cert_using_config_no_regions(self):
        renew, cert, inst = setup_config("")
        ret = renew.install_root_cert_using_config(inst.name, cert.name)
        self.assertFalse(ret)
        self.assertTrue(renew.HasLogMessage("No regions found in:"))

    def test_install_root_cert_using_config_invalid_region(self):
        renew, cert, inst = setup_config("region=aaa")
        cert.write_root("type_ibmshare_root_bbb.crt")
        ret = renew.install_root_cert_using_config(inst.name, cert.name)
        self.assertFalse(ret)
        self.assertTrue(renew.HasLogMessage(
            "No root CA cert found for region: aaa"))

    def test_install_root_cert_using_config_invalid_region2(self):
        renew, cert, inst = setup_config("region=aaa")
        ret = renew.install_root_cert_using_config(inst.name, cert.name)
        cert.write_root("type_ibmshare_root_aaa1.crt",
                        "type_ibmshare_root_aaa2.crt")
        ret = renew.install_root_cert_using_config(inst.name, cert.name)
        self.assertFalse(ret)
        self.assertTrue(renew.HasLogMessage(
            "No root CA cert found for region: aaa"))

    def test_install_root_cert_using_config_regions_all_no_certs(self):
        renew, cert, inst = setup_config("region=all")
        ret = renew.install_root_cert_using_config(inst.name, cert.name)
        self.assertFalse(ret)
        self.assertTrue(renew.HasLogMessage(
            "Ensure root CA certs are present in: "))

    def test_install_root_cert_using_config_regions_all_2certs(self):
        renew, cert, inst = setup_config("region=all")
        cert.write_root("type_ibmshare_root_dal.crt",
                        "type_ibmshare_root_wdc.crt")
        ret = renew.install_root_cert_using_config(inst.name, cert.name)
        self.assertTrue(ret)
        self.assertTrue(cert.certs_installed_ok())
        self.assertTrue(cert.certs_installed_count(2))

    def test_install_root_cert_using_config_region_dal(self):
        renew, cert, inst = setup_config("region = dal")
        cert.write_root("type_ibmshare_root_dal.crt")
        ret = renew.install_root_cert_using_config(inst.name, cert.name)
        self.assertTrue(ret)
        self.assertTrue(cert.certs_installed_ok())

    def test_install_root_cert_using_config_region_bad_multis(self):
        renew, cert, inst = setup_config("region = dal , all")
        ret = renew.install_root_cert_using_config(inst.name, cert.name)
        self.assertFalse(ret)
        self.assertTrue(renew.HasLogMessage(
            "Only one region entry allowed if using 'all':"))

    def test_install_root_cert_using_config_file_exists(self):
        renew, cert, inst = setup_config("region=", "region=xtc")
        cert.write_root("type_ibmshare_root_dal.crt",
                        "type_ibmshare_root_xtc.crt")
        ret = renew.install_root_cert_using_config(inst.name, cert.name)
        self.assertTrue(ret)
        self.assertTrue(cert.certs_installed_ok(
            ["type_ibmshare_root_xtc.crt"]))
        cfg = ShareConfig(None)
        self.assertEqual(cfg.get_region(), "xtc")


if __name__ == '__main__':
    unittest.main()
    test_cleanup()
