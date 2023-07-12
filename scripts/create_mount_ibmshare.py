# Copyright (c) IBM Corp. 2023. All Rights Reserved.
# Project name: VPC File Storage Mount Helper
# This project is licensed under the MIT License, see LICENSE file in the root directory.

import sys
import os
import glob
import subprocess


out_lines = []
out_imports = []

py_files = ["common",
            "config",
            "certificate_handler",
            "args_handler",
            "file_lock",
            "timer_handler",
            "metadata",
            "renew_certs",
            "mount_ibmshare"]


def get_files_in_folder(src, filter="*"):
    src = "%s/%s" % (src, filter)
    nfiles = []
    for file in glob.glob(src):
        if os.path.isfile(file):
            nfiles.append(file)
    return nfiles


def listToString(lst):
    return "\n".join(lst)


def readLines(fname):
    print("Reading:"+fname)
    return open(fname).read().splitlines()


def extract_imports(path, name, names):

    fname = os.path.join(path, name + ".py")
    lst = readLines(fname)

    for line in lst:
        if line.startswith("import") or line.startswith("from "):
            if line not in out_imports:
                for name in names:
                    if name in line:  # dont add names
                        print("Removing: "+line)
                        line = ""
                        break
                if len(line) > 0:
                    out_imports.append(line)
        else:
            if not line.startswith("#"):
                old_line = line
                for name in names:
                    str = name + "."
                    if str in line:
                        line = line.replace(str, "")
                if old_line != line:
                    print("Replacing:\n%s\n%s" % (old_line, line))
                out_lines.append(line)


def write_file(fname, txt):
    path, _ = os.path.split(fname)
    if not os.path.exists(path):
        os.makedirs(path)

    print("Create file", fname)
    with open(fname, "w") as fd:
        return fd.write(txt)
    os.chmod(fname, 755)


def do_merge(input_folder, out_filename):
    for name in py_files:
        extract_imports(input_folder, name, py_files)

    hdr = "#!/usr/bin/env python3\n##Do not edit created by merge script##\n\n"
    txt = hdr + listToString(out_imports) + listToString(out_lines)
    write_file(out_filename, txt)
    return True


def generate_config_file(src_folder):
    install_folder = src_folder.replace("/src", "/install")
    certs_folder = src_folder.replace("/src", "/install/certs/metadata")
    sys.path.insert(0, src_folder)
    from common import ShareConfig
    cfg = ShareConfig(install_folder, certs_folder)
    return cfg.create()


def main():
    ret = False
    if len(sys.argv) != 3:
        print("Format: %s <input_folder> <output_filename>" % sys.argv[0])
    else:
        try:
            src_folder = sys.argv[1]
            merged_file = sys.argv[2]
            if merged_file == "GENERATE_CONFIG":
                ret = generate_config_file(src_folder)
            else:
                ret = do_merge(src_folder, merged_file)
        except Exception as ex:
            print("Exception:", str(ex))
            ret = False
    sys.exit(0 if ret else 1)  # success or failure


if __name__ == '__main__':
    main()
