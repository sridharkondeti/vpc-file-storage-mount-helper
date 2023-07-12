# Copyright (c) IBM Corp. 2023. All Rights Reserved.
# Project name: VPC File Storage Mount Helper
# This project is licensed under the MIT License, see LICENSE file in the root directory.

from unittest.mock import MagicMock
from unittest import mock
import unittest
import metadata
from test_common import *
from common import *
import socket
import ssl
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
import io
import json


def newJRequest(data=None, ex=None):
    req = metadata.JsonRequest()
    req.url = "http://ibm.com"
    req.EnableLogStore()
    req.SetDebugEnabled()
    if ex:
        req.do_urlopen = MagicMock(side_effect=ex)
    elif data:
        data = json.dumps(data).encode('utf-8')
        req.do_urlopen = MagicMock(return_value=io.BytesIO(data))

    return req


def newMetadata():
    meta = metadata.Metadata()
    meta.EnableLogStore()
    return meta


def newRequest(action, ret, resp):
    req = newJRequest()
    if action == "post":
        req.post = MagicMock(return_value=ret)
    else:
        req.put = MagicMock(return_value=ret)

    req.response = resp
    meta = newMetadata()
    meta.new_request = MagicMock()
    meta.new_request.return_value = req
    return meta, req


class TestJsonRequest(unittest.TestCase):

    @mock.patch('metadata.META_IP', "www.ibm.com")
    def test_metadata_service_available_true(self):
        meta = newMetadata()
        self.assertTrue(meta.is_metadata_service_available())

    @mock.patch('metadata.META_IP', "www.does.not.exist")
    def test_metadata_service_available_false(self):
        meta = newMetadata()
        self.assertFalse(meta.is_metadata_service_available())

    def test_get_out_missing_field(self):
        req = newJRequest()
        req.response = {}
        val = req.get_out("aaa")
        self.assertIsNone(val)
        self.assertTrue(req.HasLogMessage("Field missing from response"))

    def test_get_out_ok(self):
        req = newJRequest()
        req.response = {"field1": "val1"}
        val = req.get_out("field1")
        self.assertEqual(val, "val1")

    def test_get_out_array_ok(self):
        req = newJRequest()
        req.response = {"array": ["one", "two"]}
        val = req.get_out("array:1")
        self.assertEqual(val, "two")

    def test_get_out_array_bad_index(self):
        req = newJRequest()
        req.response = {"array": []}
        val = req.get_out("array:0")
        self.assertIsNone(val)
        self.assertTrue(req.HasLogMessage("Index out of range"))

    def test_get_resp_json_ok(self):
        data = {"field1": "val1"}
        resp = io.BytesIO(json.dumps(data).encode('utf-8'))
        req = newJRequest()
        ret = req.set_resp_json(resp)
        self.assertTrue(ret)
        self.assertEqual(req.response, data)

    def test_get_resp_json_invalid_json(self):
        resp = io.BytesIO("bad json".encode('utf-8'))
        req = newJRequest()
        ret = req.set_resp_json(resp)
        self.assertFalse(ret)

    def test_get_resp_json_invalid_io_object(self):
        req = newJRequest()
        ret = req.set_resp_json(None)
        self.assertFalse(ret)

    def test_do_request_test_each_error(self):
        array = [(URLError("test"), "Url Error"),
                 (socket.timeout(), "Socket Timeout"),
                 (Exception("test"), "UnknownException"),
                 (HTTPError('http://ibm.com', 500,
                  'Internal Error', {}, None), "Http Error")]

        for ex, descr in array:
            req = newJRequest(ex=ex)
            ret = req.do_request("GET")
            self.assertFalse(ret)
            self.assertTrue(req.HasLogMessage(descr))

    def test_do_request_ok(self):
        req = newJRequest(data={"field1": "val1"})
        ret = req.do_request("GET")
        self.assertTrue(ret)
        self.assertEqual(req.get_out("field1"), "val1")


class TestMetadata(unittest.TestCase):
    def test_new_request_with_token(self):
        metadata.META_VERSION = "myVersion"
        meta = newMetadata()
        req = meta.new_request("my/Url", "myToken")
        self.assertEqual(req.url, "http://169.254.169.254/my/Url")
        self.assertEqual(req.params, {'version': 'myVersion'})
        self.assertEqual(
            req.headers, {'Accept': 'application/json', 'Authorization': 'Bearer myToken'})

    def test_new_request_ssl(self):
        meta = newMetadata()
        meta.port= 443
        req = meta.new_request("my/Url")
        self.assertEqual(req.url, "https://169.254.169.254/my/Url")
        self.assertFalse(req.context.check_hostname)
        self.assertEqual(req.context.verify_mode, ssl.CERT_NONE)


    def test_new_request_no_token(self):
        meta = newMetadata()
        req = meta.new_request("my/Url")
        self.assertEqual(req.url, "http://169.254.169.254/my/Url")
        self.assertEqual(req.headers, {'Accept': 'application/json'})
        self.assertIsNone(req.context)

    def test_set_private_key_good(self):
        meta = newMetadata()
        ret = meta.set_private_key(TEST_PRIVATE_KEY)
        self.assertTrue(ret)
        self.assertEqual(meta.private_key, TEST_PRIVATE_KEY)

    def test_set_private_key_bad(self):
        meta = newMetadata()
        ret = meta.set_private_key("invalid private key")
        self.assertFalse(ret)

    def test_new_private_key(self):
        meta = newMetadata()
        meta.private_key = ""
        ret = meta.new_private_key()
        self.assertTrue(ret)
        self.assertTrue(len(meta.private_key) > 0)

    def test_generate_csr_good(self):
        meta = newMetadata()
        meta.new_private_key()
        ret = meta.new_certificate_signing_request()
        self.assertTrue(ret)
        self.assertTrue(len(meta.csr) > 0)

    def test_generate_csr_bad(self):
        meta = newMetadata()
        ret = meta.new_certificate_signing_request()
        self.assertFalse(ret)
        self.assertIsNone(meta.csr)

    def test_generate_certs_no_csr(self):
        meta = newMetadata()
        meta.token = "myToken"
        ret = meta.generate_certs()
        self.assertFalse(ret)
        self.assertTrue(meta.HasLogMessage("Token and csr must be set"))

    def test_generate_certs_no_token(self):
        meta = newMetadata()
        meta.csr = "myCsr"
        ret = meta.generate_certs()
        self.assertFalse(ret)
        self.assertTrue(meta.HasLogMessage("Token and csr must be set"))

    def test_generate_certs_post_fails(self):
        meta, req = newRequest("post", False, {})
        meta.csr = "myCsr"
        meta.token = "myToken"
        ret = meta.generate_certs()
        self.assertFalse(ret)
        self.assertEqual(req.post.call_count, 1)

    def test_generate_certs_ok(self):
        resp = {"certificates": [
            TEST_CERT, TEST_CERT], "created_at": "ca", "expires_at": "ea"}
        meta, req = newRequest("post", True, resp)
        meta.csr = "myCsr"
        meta.token = "myToken"
        ret = meta.generate_certs()
        self.assertTrue(ret)
        self.assertEqual(req.data, '{"csr": "myCsr", "expires_in": 3600}')

        self.assertEqual(meta.cert, TEST_CERT)
        self.assertEqual(meta.cert_int_ca, TEST_CERT)
        self.assertEqual(meta.created_at, "ca")
        self.assertEqual(meta.expires_at, "ea")

    def test_get_token_good(self):
        meta, req = newRequest("put", True, {"access_token": "myToken"})
        ret = meta.get_token()
        self.assertTrue(ret)
        self.assertEqual(meta.token, "myToken")
        self.assertEqual(req.put.call_count, 1)

    def test_get_token_empty_access_token(self):
        meta, _ = newRequest("put", True, {"access_token": None})
        ret = meta.get_token()
        self.assertFalse(ret)
        self.assertEqual(meta.token, "")

    def test_get_token_put_fail(self):
        meta, req = newRequest("put", False, None)
        ret = meta.get_token()
        self.assertFalse(ret)
        self.assertEqual(req.put.call_count, 1)


if __name__ == '__main__':
    unittest.main()
