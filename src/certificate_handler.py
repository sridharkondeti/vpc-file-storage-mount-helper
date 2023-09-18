#!/usr/bin/env python3
#
# Copyright (c) IBM Corp. 2023. All Rights Reserved.
# Project name: VPC File Storage Mount Helper
# This project is licensed under the MIT License, see LICENSE file in the root directory.


from datetime import datetime, timezone
from common import *

RSA_KEY_LENGTH = 4096
CERT_VALID_LIFE_REMAINS = 0.3
OPENSSL_CSR_SUBJECT = "/C=US/ST=IL/L=Chicago/O=IBM Corporation/OU=IBM Software Group"
ALERT_CA_BEFORE = 270


class CryptoX509:
    def __init__(self):
        self.not_after = None
        self.not_before = None
        self.subject = None
        self.issuer = None

    def set_subject(self, data):
        self.subject = data

    def set_issuer(self, data):
        self.issuer = data

    def convert_date(self, dt):
        if dt:
            dt = datetime.strptime(dt, "%b %d %H:%M:%S %Y GMT")
            dt = to_utc(dt)
        return dt

    def set_dates(self, nbefore, nafter):
        self.not_before = self.convert_date(nbefore)
        self.not_after = self.convert_date(nafter)
        return self.not_before and self.not_after


class CertificateHandler(MountHelperBase):
    """Class to handle certificate expiration."""

    def __init__(self):
        self.token = ''
        self.crypto_x509 = None

    def get_ipsec_mgr(self):
        if not LocalInstall.get_ipsec_mgr():
            raise Exception("Ipsec not installed")
        return LocalInstall.get_ipsec_mgr()

    def is_loaded(self):
        return not (self.crypto_x509 is None)

    def cert_filename(self):
        return self.get_ipsec_mgr().cert_filename()

    def int_ca_filename(self):
        return self.get_ipsec_mgr().int_ca_filename()

    def root_ca_filename(self):
        return self.get_ipsec_mgr().root_ca_filename()

    # root CA cert must be installed
    def root_cert_installed(self):
        return len(self.get_ipsec_mgr().root_cert_filenames()) > 0

    def load_certificate(self):
        return self.load_certificate_by_filename(self.cert_filename())

    def load_int_ca_certificate(self):
        return self.load_certificate_by_filename(self.int_ca_filename())

    def load_root_ca_certificate(self):
        return self.load_certificate_by_filename(self.root_ca_filename())

    def run_openssl(self, cmd, descr):
        openssl_cmd = ["openssl"] + cmd
        return self.RunCmd(openssl_cmd, descr)

    def load_certificate_by_filename(self, fpath):
        self.crypto_x509 = None
        if self.FileExists(fpath):
            out = self.run_openssl(["x509", "-in", fpath, "-noout", "-dates","-subject","-issuer"],
                                   "LoadCert")
            if out:
                crt = CryptoX509()
                if crt.set_dates(out.get_stdout_val("notBefore=", True),
                                 out.get_stdout_val("notAfter=", True)):
                    crt.set_subject(out.get_stdout_val("subject=", True))
                    crt.set_issuer(out.get_stdout_val("issuer=", True))
                    self.crypto_x509 = crt
        return self.is_loaded()

    def get_subject(self):
        return self.crypto_x509.subject

    def get_issuer(self):
        return self.crypto_x509.issuer

    def load_cert(self, data):
        try:
            with TempFile(data) as cert:
                return self.load_certificate_by_filename(cert.filename)
        except Exception as ex:
            self.LogException('LoadX509Certificate', ex)
        return None

    def get_certificate_not_after_date(self):
        if not self.is_loaded():
            return None
        return self.crypto_x509.not_after

    def get_certificate_not_before_date(self):
        if not self.is_loaded():
            return None
        return self.crypto_x509.not_before

    def get_current_time(self):
        return get_utc_now()

    def check_ca_certs_validity(self, ca_cert = ""):
        assert self.is_loaded()
        before = self.get_certificate_not_before_date()
        after = self.get_certificate_not_after_date()
 
        diff = after - before
        days = divmod(diff.total_seconds(), 60*60*24)

        alert_at = get_utc_date(after, days=-ALERT_CA_BEFORE)
        if alert_at < self.get_current_time():
            self.LogWarn(ca_cert + " CA certificate will be expired at: " + str(after) +
                         " Download the latest mount helper version")
        return True

    def get_cert_renewal_date(self):
        assert self.is_loaded()
        before = self.get_certificate_not_before_date()
        after = self.get_certificate_not_after_date()

        diff = after - before
        mins = divmod(diff.total_seconds(), 60)
        renew_mins = mins[0] * CERT_VALID_LIFE_REMAINS

        # we can renew cert from this date
        can_renew_at = get_utc_date(after, minutes=-renew_mins)
        self.LogDebug("Certificate will be renewed at: " +
                      utc_format(can_renew_at))
        return can_renew_at

    def is_certificate_expired(self):
        exp = self.get_certificate_not_after_date()
        if exp < self.get_current_time():
            self.LogWarn("Certificate expired at: " +
                         utc_format(exp))
            return True
        return False

    def is_certificate_eligible_for_renewal(self):
        if not self.is_loaded():
            return None
        if self.is_certificate_expired():
            return True
        return self.get_cert_renewal_date() <= self.get_current_time()

    # Method to get timestamp when certs will be renewed.
    def get_certificate_renew_timestamp(self):
        if not self.is_loaded():
            return None

        if self.is_certificate_expired():
            return self.get_current_time()

        rdate = self.get_cert_renewal_date()
        if rdate < self.get_current_time():
            return self.get_current_time()

        return rdate

    def load_private_key(self, data):
        try:
            if not is_empty(data):
                with TempFile(data) as key:
                    if self.run_openssl(["rsa", "-in", key.filename, "-check"],
                                        "LoadPrivateKey"):
                        return key
        except Exception as ex:
            self.LogException('LoadX509PrivateKey', ex)
        return None

    def generate_private_key(self):
        with TempFile() as key:
            out = self.run_openssl(["genpkey",
                                    "-algorithm", "RSA",
                                   "-out", key.filename,
                                    "-outform", "PEM",
                                    "-pkeyopt", "rsa_keygen_bits:" + str(RSA_KEY_LENGTH)],
                                   "GenPrivateKey")
            if out:
                return key.read()
        return None

    # a helper function to check csr is ok
    def validate_csr(self, csr_txt):
        csr_txt = csr_txt.replace("\\n", "\n")
        with TempFile(csr_txt) as csr:
            cmd = ["req", "-in", csr.filename, "-text", "-noout", "-verify"]
            out = self.run_openssl(cmd, "CheckCSR")
            return out is not None

    def get_digest(self):
        return "-sha256"

    def generate_csr(self, private_key):
        # openssl req -out server.csr -key server.key -new
        digest = self.get_digest()
        with TempFile(private_key) as key:
            with TempFile() as csr:
                cmd = ["req", "-nodes", digest, "-new",
                       "-subj", OPENSSL_CSR_SUBJECT,
                       "-out", csr.filename,
                       "-key", key.filename]
                out = self.run_openssl(cmd, "GenCSR")
                if out:
                    csr_txt = csr.read()
                    csr_txt = csr_txt.replace("\n", "\\n")
                    return csr_txt
        return None
