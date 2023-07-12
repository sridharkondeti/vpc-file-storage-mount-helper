# Copyright (c) IBM Corp. 2023. All Rights Reserved.
# Project name: VPC File Storage Mount Helper
# This project is licensed under the MIT License, see LICENSE file in the root directory.

import certificate_handler
import os
import unittest
from unittest.mock import MagicMock
from test_common import *
from datetime import datetime, timedelta
from config import to_utc


TEST_CERT_FILE = '/tmp/testcert_1202.cer'
FAKE_CERT_FILE = '/tmp/testcert_1202.cer_not_exists'
RSA_KEY_LENGTH = 4096


TEST_DATE_FMT = "%b-%d-%Y %H:%M:%S"


def write_cert_file():
    write_file(TEST_CERT_FILE, TEST_CERT)


def load_test_cert(fake=False):
    co = certificate_handler.CertificateHandler()
    co.SetDebugEnabled()
    co.cert_filename = MagicMock()
    co.cert_filename.return_value = TEST_CERT_FILE if not fake else FAKE_CERT_FILE
    co.load_certificate()
    return co


def load_fake_cert():
    return load_test_cert(True)


def date_to_str(adate):
    return adate.strftime(TEST_DATE_FMT)


def set_current_time(co, str_date):
    dt = datetime.strptime(str_date, TEST_DATE_FMT)
    co.get_current_time = MagicMock(return_value=to_utc(dt))


class TestCertificateHandler(unittest.TestCase):
    def test_get_certificate_not_after_date(self):
        write_cert_file()
        expected = 'Nov-11-2022 02:52:57'
        co = load_test_cert()
        not_after = co.get_certificate_not_after_date()
        self.assertEqual(date_to_str(not_after), expected)

    def test_fake_certificate_dates_are_none(self):
        co = load_fake_cert()
        self.assertFalse(co.is_loaded())
        self.assertIsNone(co.get_certificate_not_before_date())
        self.assertIsNone(co.get_certificate_not_after_date())
        self.assertIsNone(co.is_certificate_eligible_for_renewal())

    def test_get_certificate_not_before_date(self):
        write_cert_file()
        expected = 'Aug-11-2022 20:52:27'
        co = load_test_cert()
        not_before = co.get_certificate_not_before_date()
        self.assertEqual(date_to_str(not_before), expected)

    def test_is_invalid_certificate_eligible_for_renewal_false(self):
        co = load_test_cert()
        set_current_time(co, "Sep-01-2022 20:52:27")
        self.assertFalse(co.is_certificate_eligible_for_renewal())

    def test_get_certificate_renew_timestamp_expired_cert(self):
        write_cert_file()
        co = load_test_cert()
        cur_date = 'Dec-11-2022 02:52:57'
        set_current_time(co, cur_date)
        ts = co.get_certificate_renew_timestamp()
        self.assertEqual(date_to_str(ts), cur_date)

    def test_get_certificate_renew_timestamp_expires_in_one_hour(self):
        write_cert_file()
        co = load_test_cert()
        cur_time = "Nov-11-2022 01:52:57"
        expiry = 'Nov-11-2022 02:52:57'
        set_current_time(co, cur_time)
        ts = co.get_certificate_renew_timestamp()
        self.assertEqual(date_to_str(ts), cur_time)

    def test_get_certificate_renew_timestamp_expires_in_future(self):
        write_cert_file()
        co = load_test_cert()
        cur_time = "Aug-24-2022 01:52:57"
        renew_date = "Oct-14-2022 17:52:57"
        set_current_time(co, cur_time)
        ts = co.get_certificate_renew_timestamp()
        self.assertEqual(date_to_str(ts), renew_date)

    def test_generate_private_key(self):
        co = load_test_cert()
        pkey = co.generate_private_key()
        self.assertTrue(len(pkey) > 0)

    def test_generate_csr(self):
        co = load_test_cert()
        pkey = co.generate_private_key()
        csr = co.generate_csr(pkey)
        self.assertTrue(len(csr) > 0)
        self.assertTrue(co.validate_csr(csr))

    def test_generate_csr_bad_private_key(self):
        co = load_test_cert()
        csr = co.generate_csr("")
        self.assertEqual(csr, None)

    def test_generate_csr_bad_digest(self):
        co = load_test_cert()
        co.get_digest = MagicMock(return_value="-sha999")
        pkey = co.generate_private_key()
        csr = co.generate_csr(pkey)
        self.assertEqual(csr, None)

    def test_is_certificate_eligible_for_renewal(self):
        write_cert_file()
        co = load_test_cert()
        set_current_time(co, "Oct-15-2022 20:52:27")
        self.assertTrue(co.is_certificate_eligible_for_renewal())


if __name__ == "__main__":
    unittest.main()
