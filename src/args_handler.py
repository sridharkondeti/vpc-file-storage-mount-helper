#!/usr/bin/env python3
#
# Copyright (c) IBM Corp. 2023. All Rights Reserved.
# Project name: VPC File Storage Mount Helper
# This project is licensed under the MIT License, see LICENSE file in the root directory.

import argparse
from enum import Enum
from common import *

ESSENTIAL_OPTIONS = 'sec=sys,nfsvers=4.1'
MOUNT = 'mount'
NFS_VERSION = 'nfs4'
MOUNT_T_OPTION = '-t'
MOUNT_O_OPTION = '-o'
MOUNT_VERBOSE_FLAG = '-v'
RENEW_CERTIFICATE_FLAG = "-RENEW_CERTIFICATE_NOW"
INSTALL_ROOT_CERT = "-INSTALL_ROOT_CERT"
SECURE_OPTION = 'secure'
SECURE_ARG = 'true'
SBIN_SCRIPT = "/sbin/mount.ibmshare"
TEARDOWN_APP = "-TEARDOWN_APP"


class AppRunType(object):
    SETUP = "SUP"
    TEARDOWN = "TDN"
    RENEW = "REN"
    MOUNT = "MNT"

    def __init__(self, value):
        self.value = value

    def is_setup(self):
        return self.value == self.SETUP

    def is_teardown(self):
        return self.value == self.TEARDOWN

    def is_renew(self):
        return self.value == self.RENEW

    def is_mount(self):
        return self.value == self.MOUNT


class ArgsHandler(MountHelperBase):
    """Class to process nfs mount command arguments."""
    mount_args = None

    def __init__(self):
        self.ip_address = None
        self.mount_point = None
        self.mount_path = None
        self.mount_source = None
        self.options = None
        self.is_secure = False

    def parse(self):
        is_error = False

        def parse_error(errmsg):
            nonlocal is_error
            is_error = True
            self.LogError(errmsg)
        parser = argparse.ArgumentParser()
        parser.error = parse_error
        parser.add_argument('Source', default="")  # nfs_host:path
        parser.add_argument('Destination', default="")  # mount point
        parser.add_argument('-o', default="")
        args, _ = parser.parse_known_args()
        if is_error:
            return False
        self.mount_source = args.Source
        self.mount_point = args.Destination
        self.ip_address, self.mount_path = NfsMount.extract_source(
            self.mount_source)
        if not self.ip_address or not self.mount_path:
            return self.LogError('Provide the mount source as <nfs_host>:<path>(' + self.mount_source + ').')
        if len(self.mount_point) <= 0:
            return self.LogError("Provide the mount point to mount on local host.")
        self.options, self.is_secure = self.get_mount_options(args.o)
        return True

    @staticmethod
    def get_mount_args():
        args = ArgsHandler()
        return args if args.parse() else None

    @staticmethod
    def is_renew_certificate():
        return SysApp.has_arg(RENEW_CERTIFICATE_FLAG)

    @staticmethod
    def is_app_setup():
        return SysApp.has_arg(INSTALL_ROOT_CERT)

    @staticmethod
    def is_app_teardown():
        return SysApp.has_arg(TEARDOWN_APP)

    def get_renew_certificate_cmd_line(self):
        return SBIN_SCRIPT + " " + RENEW_CERTIFICATE_FLAG

    @staticmethod
    def is_debug_enabled():
        args = str(SysApp.argv())
        return MOUNT_VERBOSE_FLAG in args

    @staticmethod
    def get_app_run_type():
        run_type = AppRunType.MOUNT
        if ArgsHandler.is_app_setup():
            run_type = AppRunType.SETUP
        elif ArgsHandler.is_app_teardown():
            run_type = AppRunType.TEARDOWN
        elif ArgsHandler.is_renew_certificate():
            run_type = AppRunType.RENEW
        return AppRunType(run_type)

    @staticmethod
    def set_logging_level():
        rt = ArgsHandler.get_app_run_type()
        if ArgsHandler.is_debug_enabled() or rt.is_setup() or rt.is_teardown():
            MountHelperLogger().SetDebugEnabled()
        MountHelperLogger().SetLogToFileEnabled()
        MountHelperLogger.log_prefix = rt.value

    # Method to return all -o option list of mount command.
    def get_mount_options(self, opts_in):
        is_secure = False
        options = opts_in.split(',')
        o_options = []
        for option in options:
            if not SECURE_OPTION in option.lower():
                o_options.append(option)
            elif SECURE_ARG in option.lower().split('='):
                is_secure = True

        return ','.join(o_options), is_secure

    # Method to contruct mount command to run finally.
    def get_mount_cmd_line(self):
        assert len(self.mount_source) > 0
        cmd = [MOUNT, MOUNT_T_OPTION, NFS_VERSION, MOUNT_O_OPTION, ','.join(
            [ESSENTIAL_OPTIONS, self.options]), self.mount_source,  self.mount_point]

        # pass on the verbose flag
        if self.is_debug_enabled():
            cmd.append(MOUNT_VERBOSE_FLAG)

        return cmd
