#!/usr/bin/env python3
#
# Copyright (c) IBM Corp. 2023. All Rights Reserved.
# Project name: VPC File Storage Mount Helper
# This project is licensed under the MIT License, see LICENSE file in the root directory.


from args_handler import ArgsHandler
from common import *
import file_lock
import timer_handler
from renew_certs import RenewCerts
from config import LocalInstall, StrongSwanConfig


class MountIbmshare(MountHelperBase):
    def __init__(self):
        self.mounts = []
        self.lockhandler = file_lock.LockHandler.mount_share_lock()

    def set_installed_ipsec(self):
        ss_obj = StrongSwanConfig()
        if ss_obj.set_version():
            LocalInstall.set_ipsec_mgr(ss_obj)
            return True
        self.LogError("IPsec installation failed, check the charon logs.")
        return False

    def get_ipsec_mgr(self):
        return LocalInstall.get_ipsec_mgr()

    def app_setup(self):
        if LocalInstall.setup():
            ipsec = self.get_ipsec_mgr()
            if ipsec:
                ipsec.remove_all_configs(unused=True)
                if ipsec.setup():
                    cert_path = SysApp.argv(2)
                    return RenewCerts().install_root_cert(cert_path)
        self.LogError("Installation failed.", code=SysApp.ERR_APP_INSTALL)
        return False

    def app_teardown(self):
        self.LogDebug("TearDown starting")
        ipsec = self.get_ipsec_mgr()
        if ipsec:
            ipsec.remove_all_certs()
            ipsec.remove_all_configs()
        LocalInstall.teardown()
        timer_handler.TimerHandler().teardown()
        self.LogDebug("TearDown complete")
        return True

    def renew_certs(self):
        return RenewCerts().renew_cert_cmd_line()

    def lock(self):
        return self.lockhandler.grab_blocking_lock()

    def unlock(self):
        return self.lockhandler.release_lock()

   # Method to check whether nfs share is already mounted.
    def is_share_mounted(self, ip_address, mount_path):
        self.mounts = NfsMount().load_nfs_mounts()
        if self.mounts is None:
            return True  # Force app to exit app
        for mount in self.mounts:
            if mount.ip == ip_address and mount.mount_path == mount_path:
                self.LogUser('Share is already mounted at: ' +
                             mount.mounted_at)
                return True
        return False

    def mount(self, args):
        if self.is_share_mounted(args.ip_address, args.mount_path):
            return False

        if not args.is_secure:
            self.LogUser("Non-IPsec mount requested.")
            ipsec = self.get_ipsec_mgr()
            if ipsec:
                ipsec.remove_config(args.ip_address)
                ipsec.reload_config()
        else:
            cert = RenewCerts()
            if not cert.root_cert_installed():
                self.LogError("Root Certificate must be installed.")
                return False

            if not cert.load_certificate():
                if not cert.get_initial_certs():
                    return False

            if cert.is_certificate_eligible_for_renewal():
                if not cert.renew_cert_now():
                    if cert.is_certificate_expired():
                        return False
                    self.LogWarn("Cert has not expired, so will continue.")

            ipsec = cert.get_ipsec_mgr()
            if not ipsec.is_running():
                return False
            if not ipsec.create_config(args.ip_address):
                return False
            ipsec.cleanup_unused_configs(self.mounts)
            ipsec.is_reload = True
            if not ipsec.reload_config():
                return False
            # ipsec.connect(args.ip_address)

        self.unlock()
        out = self.RunCmd(args.get_mount_cmd_line(), "MountCmd", ret_out=True)
        if not out or out.is_error():
            # we pass back the mount command exit code
            exit_code = SysApp.ERR_MOUNT + out.returncode if out else SysApp.ERR_MOUNT
            return self.LogError("Share mount failed.", code=exit_code)

        self.ca_certs_alert()
        self.LogUser("Share successfully mounted:" + out.stdout)
        return True

    # Check int and root CA certs validity.
    def ca_certs_alert(self):
        cert = RenewCerts()
        if not cert.load_int_ca_certificate():
            return False
        cert.check_ca_certs_validity("Int")
        if not cert.load_root_ca_certificate():
            return False
        cert.check_ca_certs_validity("Root")
        return True

    def run(self):
        if not SysApp.is_root():
            return self.LogError("Run the mount as super user.", code=SysApp.ERR_NOT_SUPER_USER)

        ret = False
        try:
            ArgsHandler.set_logging_level()
            self.set_installed_ipsec()

            rt = ArgsHandler.get_app_run_type()
            if rt.is_setup():
                ret = self.app_setup()
            elif rt.is_teardown():
                ret = self.app_teardown()
            elif rt.is_renew():
                ret = self.renew_certs()
                self.ca_certs_alert()
            elif rt.is_mount():
                args = ArgsHandler.get_mount_args()
                if args:
                    self.lock()
                    ret = self.mount(args)
                    self.unlock()
        except Exception as ex:
            self.LogException("AppRun", ex)
            self.unlock()
        return ret


# Entry method for mount helper processing.
def main():
    ret = MountIbmshare().run()
    SysApp.exit(ret)


if __name__ == '__main__':
    main()
