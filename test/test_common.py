# Copyright (c) IBM Corp. 2023. All Rights Reserved.
# Project name: VPC File Storage Mount Helper
# This project is licensed under the MIT License, see LICENSE file in the root directory.

from unittest.mock import MagicMock
from unittest import mock
import os
import tempfile
import random
from config import SubProcess
from common import *
import shutil

TEST_CERT = """-----BEGIN CERTIFICATE-----
MIIDSzCCAjOgAwIBAgIUKphcbE+MoNzNsGfDtEPMcwb/Ib8wDQYJKoZIhvcNAQEL
BQAwIDEeMBwGA1UEAxMVcmZvcy1pbnRlcm1lZGlhdGUtY2ExMB4XDTIyMDgxMTIw
NTIyN1oXDTIyMTExMTAyNTI1N1owFDESMBAGA1UEAxMJbG9jYWxob3N0MIIBIjAN
BgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA3CxTVI/XNTKsqKdCH8o6tORFz4p/
59vb3xpeM8vn8nHlmow0XoMG3usrXPoWdYTQiCYNndw5+LzvD209gM52T4aUOER9
rtBcOvIt5l7dU+cuVhnuABB40VB6NxU/pbQfZY64Jsen+z3sSGQnBpeaSR5kZqV4
X4eXSCHf7IVXIFmCKPAOTD615PmqbL9nMWeN9cS1oZh45jesAI/XdrGEY99k817C
Er3s4stnSQYhxls2rcGDjz8Yw/i1CQM6d2+uZwDuQyRCUU/HppVO85alSDP7ws7i
ZVOGc1/ITWJ1bIKHNnyCGwIIhNbcT43wOKHjBca9JcQnqJ8hMUCArix5WwIDAQAB
o4GIMIGFMA4GA1UdDwEB/wQEAwIDqDAdBgNVHSUEFjAUBggrBgEFBQcDAQYIKwYB
BQUHAwIwHQYDVR0OBBYEFLMESvr5M5w979kzNeZmsz+8xV92MB8GA1UdIwQYMBaA
FHhkSG/F2B5LNNPTwtL3lTetStd7MBQGA1UdEQQNMAuCCWxvY2FsaG9zdDANBgkq
hkiG9w0BAQsFAAOCAQEAWB3J+S9tJzNQDzoM+4RfA+4LHAJ6k4a4lB2JxsznAXbg
0VBqVgTDw6y5tuTzkDUnF6xyZmzgogWHRPoq/G6SAbT1DmOC5lcJ483vkG98x7QE
LLk0Eh3g/aaUP9MVU8KcG239KomeNqL94Lz1ziLKPGVyuFAX6OBBT5tgOExZcejV
I8TolDkCUno0LQ2wORjUpxwTnwq0U5Z5ZlhVDc1jRDF+573rrxc+Wbomv/TnKTGq
T7+4GIeaWybZAwR8ku7vlHZg9mYehphiqc7It4zJpMcVISuK7BKFhqD43i3dBMz1
RR5qgsMaVVlG9+bUwX/ByRtSJRk7eh8TEyg6vM2tNg==
-----END CERTIFICATE-----"""

TEST_PRIVATE_KEY = '''-----BEGIN PRIVATE KEY-----
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
/agtWgm9fMVRS4xb9m73pY6Hi/L7
-----END PRIVATE KEY-----'''

TEST_ROOT_CERT = '''-----BEGIN CERTIFICATE-----
MIIDNTCCAh2gAwIBAgIUCAv1EI1FGdubbYyka+MaAQsCJQQwDQYJKoZIhvcNAQEL
BQAwFjEUMBIGA1UEAxMLZWl0LXJvb3QtY2EwHhcNMjIwNzAxMTUzNzQyWhcNMzIw
NjI4MTUzODEyWjAWMRQwEgYDVQQDEwtlaXQtcm9vdC1jYTCCASIwDQYJKoZIhvcN
AQEBBQADggEPADCCAQoCggEBAJ0Ytl4BlMv38+376WbLWXrmSQCgNaOxVNk0Kf9I
iXjcvDwkSTIT0rzVcC0gqdGmWE00iP56qX26RbOquL9dEjDYSV6AyDcZrNKEp3Ol
YEUFNhQa0EL9aKw+mu6tOMTMx5DEDuyra/f1Ya2s2uBTW2NDwjMEBNlcEqmYZyBn
vfbbI53gg1L5M+lscNhW4jcjg0PMV4n95NSFUbUvgdl+0c5BiGVUSyHPHrnAHIoD
XffXq/MnigMhDqDx7qIxQ6YVftHKLdW4e9BHgmKkvCU7KyDgxC0VpFbC26ktMLUV
DYBA7pWBp8/jPwH6RQSp6WPxeyrJXNweOvl/QlNGMtMsX28CAwEAAaN7MHkwDgYD
VR0PAQH/BAQDAgEGMA8GA1UdEwEB/wQFMAMBAf8wHQYDVR0OBBYEFBZWIib5EHhl
bT0mxZ0tgrGRho2rMB8GA1UdIwQYMBaAFBZWIib5EHhlbT0mxZ0tgrGRho2rMBYG
A1UdEQQPMA2CC2VpdC1yb290LWNhMA0GCSqGSIb3DQEBCwUAA4IBAQBvTTJRxh4m
46JRx5c0J0F/D90VoPpqk2RUnWv9wwulCeK9W47O1XNkny7362wFGUJzuhV3QtZa
uXxSlUWzfUzFM0UdfL8IEMT0bYwFzmkcJ9SJUi+4rhlJtkyhGDs7No79o2kk7Gv2
K8KNwYPRXHfYemHQmDVi3LlBw3OucXxqFDPTL37msCrLj0s2W1HAN2Gq6TZJd9BP
KtQnVB5dtvHCybOpuqoSMGQztS4YNpgaqC5WUKAH5Sw1HU04RO/1mQkKR/LQ3GBC
iT8R1HZkStVUnHX+pj/eXZftYJJolrJ3l7+8cedx+cYXE3/26V5YydPlxblXwmev
HcR3dmcTHIX1
-----END CERTIFICATE-----'''


def show(msg, tag=""):
    print(tag + "*********************************")
    print(msg)
    print("*********************************")


def remove_comments(str):
    out = []
    for line in str.split("\n"):
        if not line.startswith("#"):
            out.append(line)
    return "\n".join(out)


def write_file(fpath, data):
    with open(fpath, "w") as fp:
        fp.write(data)
    return fpath


def read_file(fpath):
    with open(fpath, "r") as fp:
        return fp.read()


def file_contains(fpath, what):
    out = read_file(fpath)
    return out.find(what) >= 0


def remove_file(fpath):
    if os.path.exists(fpath):
        os.remove(fpath)


def write_bash_file(fname, data):
    write_file(fname, "#!/bin/bash\n" + data)
    os.chmod(fname, 0o777)


def random_ip():
    return ".".join(str(random.randint(0, 255)) for _ in range(4))


class MySubProcess(object):
    def __init__(self, ret, data):
        pret = SubProcess([])
        pret.set_output(ret, data.encode(encoding='utf-8'), "")
        self.patch = mock.patch("common.SubProcess.run")
        self.func = self.patch.__enter__()
        self.func.return_value = pret

    def __enter__(self):
        return self

    def __exit__(self, exception_type, exception_value, traceback):
        self.patch.__exit__(None, None, None)
        pass


class MyTempDir():
    def __init__(self, id="1"):
        self.name = "/tmp/mount.helper.tmp" + id
        self.recreate()

    def exists(self):
        return os.path.exists(self.name)

    def mkdir(self):
        os.makedirs(self.name)

    def cleanup(self):
        if self.exists():
            shutil.rmtree(self.name)

    def recreate(self):
        self.cleanup()
        self.mkdir()

    def get_temp_filename(self, postfix=""):
        fname = os.path.join(self.name, next(
            tempfile._get_candidate_names()) + postfix)
        assert not os.path.exists(fname)
        return fname

    def write_file(self, fname, data):
        fname = make_filename(self.name, fname)
        write_file(fname, data)


test_folder = MyTempDir()


def test_cleanup():
    test_folder.cleanup()
