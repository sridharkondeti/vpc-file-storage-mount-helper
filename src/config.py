#!/usr/bin/env python3
#
# Copyright (c) IBM Corp. 2023. All Rights Reserved.
# Project name: VPC File Storage Mount Helper
# This project is licensed under the MIT License, see LICENSE file in the root directory.


import glob
import os
import shutil
from datetime import datetime
from common import *


class IpsecConfigBase(MountHelperBase):
    CLEANUP_FILE_MIN_AGE_MINS = 60
    VERSION = None

    def __init__(self):
        self.is_reload = False

    def private_key_filename(self):
        name = "type_ibmshare.key"
        return make_filename(self.KEY_FILE_PATH, name)

    def read_private_key(self):
        return self.ReadFile(self.private_key_filename())

    def read_cert(self):
        return self.ReadFile(self.cert_filename())

    def cert_filename(self, name_only=False):
        name = "type_ibmshare.pem"
        if name_only:
            return name
        return make_filename(self.CERT_PATH, name)

    def root_cert_folder(self):
        return self.ROOT_CA_PATH

    def root_cert_filenames(self, region=""):
        filter = "type_ibmshare_root*%s*.*" % region
        return get_files_in_folder(self.root_cert_folder(), filter)

    def int_ca_filename(self, name_only=False):
        name = "type_ibmshare_int.crt"
        if name_only:
            return name
        return make_filename(self.INT_CA_PATH, name)

    def root_ca_filename(self):
        root_ca_certs = self.root_cert_filenames()
        if len(root_ca_certs) > 0:
            return root_ca_certs[0]
        return None

    def read_int_ca(self):
        return self.ReadFile(self.int_ca_filename())

    def get_config_template_text(self):
        return self.IPSEC_CONFIG_TEXT

    def get_config_template_file(self, ip):
        name = "type_ibmshare_" + ip + ".conf"
        return make_filename(self.IPSEC_CONFIG_PATH, name)

    def get_config_file_parts(self):
        return self.IPSEC_CONFIG_PATH, "type_ibmshare_", ".conf"

    def get_config(self, ip):
        fname = self.get_config_template_file(ip)
        return fname if self.FileExists(fname) else None

    def remove_config(self, ip):
        fname = self.get_config(ip)
        if fname:
            self.LogDebug("Removing unused config file: "+fname)
            self.RemoveFile(fname)
            self.is_reload = True

    def connection_name(self, ip):
        return "ibmshare-ipsec-to-" + ip.replace(".", "-")

    def create_config(self, ip):
        tags = {}

        tags["REMOTE_IP"] = ip
        tags["CONNECTION_NAME"] = self.connection_name(ip)
        tags["CLIENT_CERT_FILE"] = self.cert_filename()

        vdata = "# %s - Version %s\n" % (self.NAME, self.VERSION)
        cfg_path = self.get_config_template_file(ip)
        cfg_data = vdata + self.get_config_template_text()

        for name, value in tags.items():
            tag = "<" + name + ">"
            # assert cfg_data.find(tag) >= 0
            cfg_data = cfg_data.replace(tag, value)

        try:
            # if file exists and data the same
            # update the file modify time so it doesnt get deleted
            # before the mount operation completes
            if self.FileNoChange(cfg_path, cfg_data):
                self.LogDebug("Config data unchanged:" + cfg_path)
                dt_epoch = datetime.now().timestamp()
                os.utime(cfg_path, (dt_epoch, dt_epoch))
                return True

            if self.WriteFile(cfg_path, cfg_data, mkdir=True):
                self.LogDebug("Config file created ok:" + cfg_path)
                self.is_reload = True
                return True
        except Exception as ex:
            self.LogException("CreateConfig"+self.NAME, ex)
        return False

    # Remove any unused config files
    def cleanup_unused_configs(self, mounts,
                               age=None):
        if mounts is None:
            mounts = NfsMount().load_nfs_mounts()

        cfg_path, cfg_prefix, cfg_postfix = self.get_config_file_parts()

        def file_created_recently(fname, max_mins):
            if max_mins == 0:  # ignore file time
                return False
            st = os.stat(fname)
            fmod_time = datetime.fromtimestamp(st.st_mtime)
            duration = datetime.now() - fmod_time
            fmins, _ = divmod(duration.seconds, 60)
            return fmins <= max_mins

        def get_filename_ip(fname):
            if not fname.startswith(cfg_prefix):
                return None
            fname = fname.replace(cfg_prefix, "")
            return fname.replace(cfg_postfix, "")

        cnts = [0, 0, 0, 0]  # all/mounted/deleted/recent

        def inc_cnt(pos):
            nonlocal cnts
            cnts[pos] += 1

        files = []
        if os.path.exists(cfg_path):
            files = os.listdir(cfg_path)
        for file in files:
            inc_cnt(0)
            file_ip = get_filename_ip(file)
            if not file_ip:
                continue
            got = False
            for mount in mounts:
                if mount.ip == file_ip:
                    got = True
                    break
            if got:
                inc_cnt(1)
            else:
                fname = make_filename(cfg_path, file)
                # dont delete files created recently - a mount might be happening
                if age is None:
                    age = self.CLEANUP_FILE_MIN_AGE_MINS

                if not file_created_recently(fname, age):
                    self.remove_config(file_ip)
                    inc_cnt(2)
                else:
                    inc_cnt(3)

        msg = "%s cleanup config files Total(%s) Mounted(%d) Deleted(%d) Recent(%d)" % (
            self.NAME, cnts[0], cnts[1], cnts[2], cnts[3])
        self.LogDebug(msg)
        hasActiveMounts = cnts[1] != 0 or cnts[3] != 0
        return hasActiveMounts

    def _reload_certs(self, args):
        if self.is_reload:
            if not self.IpsecCmd(args, "ReloadCerts"):
                return False
            self.is_reload = False
        return True

    def _reload_config(self, args):
        if self.is_reload:
            if not self.IpsecCmd(args, "ReloadConfig"):
                return False
            self.is_reload = False
        return True

    def IpsecCmd(self, args, descr=""):
        cmd = self.EXE_PATH + " " + args
        if not self.RunCmd(cmd, descr):
            return SysApp.set_code(SysApp.ERR_IPSEC_CFG)
        return True

    def remove_all_configs(self, unused=False):
        if unused:
            return self.cleanup_unused_configs(None, 0)
        else:
            self.CleanupDir(self.IPSEC_CONFIG_PATH)

    def flatten_paths(self, path):
        if not os.path.exists(path):
            return self.LogError("FolderNotExist: " + path)
        self.ROOT_CA_PATH = path
        self.INT_CA_PATH = path
        self.KEY_FILE_PATH = path
        self.CERT_PATH = path
        self.IPSEC_CONFIG_PATH = path
        return True

    def remove_all_certs(self,root=False):
        self.CleanupDir(self.ROOT_CA_PATH)
        if root:
            return
        self.CleanupDir(self.INT_CA_PATH)
        self.CleanupDir(self.KEY_FILE_PATH)
        self.CleanupDir(self.CERT_PATH)

    def install_root_cert(self, name, data):
        fname = make_filename(self.root_cert_folder(), name)
        return self.write_cert(fname, data)

    def write_cert(self, fname, data):
        if self.FileNoChange(fname, data):
            self.LogDebug("Cert File NoChange:" + fname)
        else:
            if not self.WriteFile(fname, data, mkdir=True):
                return False
            self.is_reload = True
        return True

    def write_new_certs(self, cert, private_key, cert_int_ca):
        ret = False
        self.LogDebug("Renewing cert files")
        if self.write_cert(self.private_key_filename(), private_key):
            if self.write_cert(self.int_ca_filename(), cert_int_ca):
                if self.write_cert(self.cert_filename(), cert):
                    ret = True
                    if self.is_reload:
                        self.LogInfo("Certificates updated successfully")
                        return self.reload_config()
        return ret

    def set_version(self):
        self.VERSION = get_app_version(self.EXE_PATH, self.VERSION_TAG)
        if self.VERSION:
            self.LogInfo("IpSec using %s(%s)" % (self.NAME, self.VERSION))
        return self.VERSION


class StrongSwanConfig(IpsecConfigBase):
    def config_path():
        path = "/etc/swanctl"
        if not os.path.exists(path):
            # on some installs eg (Rocky)
            path = "/etc/strongswan/swanctl"
        return path

    NAME = "StrongSwan"
    VERSION_TAG = "swanctl"
    EXE_PATH = "/usr/sbin/swanctl"
    CONFIG_PATH = config_path()
    ROOT_CA_PATH = CONFIG_PATH + '/x509ca'
    INT_CA_PATH = ROOT_CA_PATH
    KEY_FILE_PATH = CONFIG_PATH + '/private'
    CERT_PATH = CONFIG_PATH + '/x509'
    IPSEC_CONFIG_PATH = CONFIG_PATH + '/conf.d'
    IPSEC_CONFIG_TEXT = """connections {
    <CONNECTION_NAME> {
        children {
            <CONNECTION_NAME> {
                esp_proposals = aes256gcm16
                mode = transport
                start_action = trap
                remote_ts = <REMOTE_IP>[any/any]
                local_ts = 0.0.0.0/0[any/any]
                rekey_time = 3600
                rekey_bytes = 0
            }
        }
        keyingtries = 3
        version = 2
        remote_addrs = <REMOTE_IP>
        rekey_time = 3600
        encap = yes
        proposals = aes256-sha384-ecp384
        local {
            certs = <CLIENT_CERT_FILE>
        }
        remote {
        id = %any
        }
    }
}
"""

    def set_version(self):
        if os.path.exists(self.EXE_PATH):
            if not super().set_version():
                # can happen with swanctl service error
                self.VERSION = "Undefined"
            return True

        return False

    def reload_certs(self, root=False):
        return self._reload_certs("--load-creds")

    def reload_config(self):
        return self._reload_config("--load-all")

    def list_connections(self):
        return self.IpsecCmd("--list-conns")

    def setup(self):
        return self.start()

    def is_running(self):
        return self.start()

    def start(self, max_secs=10):
        ss = SystemCtl("strongswan")
        secs = 0
        while secs <= max_secs:
            if not ss.is_active():
                self.LogInfo("Starting Strongswan Ipsec")
                if not ss.enable():
                    return False
                time.sleep(1)
            # just to verify that swanctl is running ok
            if self.list_connections():
                return True
            self.wait(2, "Ipsec starting")
            secs += 2
        return self.LogError("Unable to start IPsec, check charon logs")
