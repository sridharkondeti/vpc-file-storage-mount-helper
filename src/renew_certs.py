#!/usr/bin/env python3
#
# Copyright (c) IBM Corp. 2023. All Rights Reserved.
# Project name: VPC File Storage Mount Helper
# This project is licensed under the MIT License, see LICENSE file in the root directory.


import args_handler
from certificate_handler import CertificateHandler
import metadata
from common import *
import file_lock
import timer_handler

from config import LocalInstall


class RenewCerts(metadata.Metadata):
    RENEW_RETRY_DELAY = 60  # 1 minute
    RENEW_MAX_RETRIES = -1  # forever

    def __init__(self):
        super().__init__()

    def install_root_cert(self, src):
        if not metadata.USE_METADATA_SERVICE:
            return self.get_local_certs_no_metadata(src, init=True)

        return self.install_root_cert_using_config(".", src)

    def get_initial_certs(self):
        return self.run_func(self._get_initial_certs)

    def renew_cert_now(self):
        return self.run_func(self._renew_cert_now)

    def renew_cert_cmd_line(self):
        return self.run_func(self._renew_cert_cmd_line)

    # wrapper func to add lock
    def run_func(self, afunc):
        ret = False
        lockhandler = file_lock.LockHandler.renew_cert_lock()
        try:
            if lockhandler.grab_non_blocking_lock():
                ret = afunc()
        except Exception as ex:
            self.LogException("CertMgr", ex)
        lockhandler.release_lock()
        return ret

    def _get_initial_certs(self):
        cnt = 0
        self.RENEW_MAX_RETRIES = 25
        while cnt < self.RENEW_MAX_RETRIES:
            cnt += 1
            if self.metadata_renew_cert():
                return self.load_certificate()
            self.wait(self.RENEW_RETRY_DELAY,
                 "Generate cert failed, retry(" + str(cnt) + " of " + str(self.RENEW_MAX_RETRIES) + ")")
        return False

    def _renew_cert_cmd_line(self):
        cnt = 0
        self.LogInfo("Metadata renew certs.")
        while cnt < self.RENEW_MAX_RETRIES or self.RENEW_MAX_RETRIES < 0:
            cnt += 1
            # check if mount in progress
            lockhandler = file_lock.LockHandler.mount_share_lock()
            if not lockhandler.is_locked():
                hasActiveMounts = self.get_ipsec_mgr().cleanup_unused_configs(None)
                if not hasActiveMounts:
                    self.LogInfo(
                        "Will not renew cert - no nfs mounts active or pending")
                    return True  # this is ok
            if self.metadata_renew_cert():
                return True
            if not metadata.USE_METADATA_SERVICE:
                return False
            self.wait(self.RENEW_RETRY_DELAY,
                      "Renew cert failed, retry(" + str(cnt) + ")")
        return False

    def _renew_cert_now(self):
        return self._get_initial_certs()

    def metadata_get_new_certs(self):
        if not self.is_metadata_service_available():
            return self.LogError("Could not connect to Metadata service.",
                                 code=SysApp.ERR_METADATA_UNAVAILABLE)

        if not self.get_token():
            return self.LogError("Problem getting token",
                                 code=SysApp.ERR_METADATA_TOKEN)

        ipsec = self.get_ipsec_mgr()
        private_key = ipsec.read_private_key()
        if private_key:
            self.LogDebug("RenewCert:Use existing private key")
            private_key = self.set_private_key(private_key)

        if not private_key:
            self.new_private_key()

        if not self.new_certificate_signing_request():
            return self.LogError("Problem with generating signing request.")

        if not self.generate_certs():
            return self.LogError("Generate certs failed.",
                                 code=SysApp.ERR_METADATA_CERT_RENEW)
        return True

    def metadata_renew_cert(self):
        if not metadata.USE_METADATA_SERVICE:
            self.LogDebug("Checking for local certs in: " +
                          LocalInstall.cert_path())
            return self.get_local_certs_no_metadata(LocalInstall.cert_path(), init=False)

        if not self.metadata_get_new_certs():
            return False

        ipsec = self.get_ipsec_mgr()
        ipsec.write_new_certs(self.cert, self.private_key, self.cert_int_ca)
        return self.schedule_next_renewal()

    def schedule_next_renewal(self):
        if not self.load_certificate():
            return False

        renew_time_stamp = self.get_certificate_renew_timestamp()
        if not renew_time_stamp:
            self.LogError(
                'Certificate file not found or unable to load cert file.')
            return False

        ao = args_handler.ArgsHandler()
        to = timer_handler.TimerHandler()
        ret = to.schedule_certs_renewal(
            renew_time_stamp, ao.get_renew_certificate_cmd_line())
        return ret

    def install_root_cert_using_config(self, install_path, cert_path):
        cfgOrig = ShareConfig(None, cert_path=cert_path)
        cfgInstall = ShareConfig(install_path, cert_path=cert_path)

        cfg = cfgInstall
        # if region set in install file - use that
        if not cfgInstall.get_region() and cfgOrig.exists():
            cfg = cfgOrig

        if not cfg.exists():
            return cfg.error("Missing configuration file:")

        regions = cfg.load_regions()
        if not regions:
            return False

        install_cas = cfg.get_files_for_regions(regions)
        if not install_cas:
            return False

        ipsec = self.get_ipsec_mgr()
        ipsec.remove_all_certs(root=True)
        for ca in install_cas:
            if not ipsec.install_root_cert(
                    get_filename(ca.fname),
                    self.ReadFile(ca.fname)):
                return False

        if cfg.name == cfgInstall.name:
            self.CopyFile(cfgInstall.name, cfgOrig.name, mkdir=True)

        return ipsec.reload_certs(root=True)

    def get_local_certs_no_metadata(self, cert_path, init):
        ipsec = self.get_ipsec_mgr()

        ipsec2 = clone_obj(ipsec)
        if not ipsec2.flatten_paths(cert_path):
            return False

        # load root CA certs
        cas = ipsec2.root_cert_filenames()
        if len(cas) > 0:
            self.LogInfo("Installing RootCA(s)")
            for ca in cas:
                if not ipsec.install_root_cert(
                        get_filename(ca),
                        self.ReadFile(ca)):
                    return False
            if not ipsec.reload_certs(root=True):
                return False
        elif init:
            return self.LogError("No root CA cert(s) found.")

        # load certs if available
        if not metadata.USE_METADATA_SERVICE:
            key = ipsec2.read_private_key()
            cert = ipsec2.read_cert()
            int_ca = ipsec2.read_int_ca()
            cnt = [key, cert, int_ca].count(None)
            if cnt == 0:
                if ipsec.write_new_certs(cert, key, int_ca):
                    return self.schedule_next_renewal()
            else:
                if cnt == 3 and init:  # ok no cert can get later
                    self.LogInfo("No certs found to install.")
                    return True

                self.LogError("Incomplete list of cert files in:" + cert_path)
                return False
        return True
