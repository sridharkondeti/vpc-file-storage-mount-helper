#!/usr/bin/env python3
#
# Copyright (c) IBM Corp. 2023. All Rights Reserved.
# Project name: VPC File Storage Mount Helper
# This project is licensed under the MIT License, see LICENSE file in the root directory.


from common import *
from certificate_handler import CertificateHandler
import json
import socket
import ssl
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode

USE_METADATA_SERVICE = True
META_IP = "169.254.169.254"
META_PORT_HTTP = 80
META_PORT_HTTPS = 443
META_URL_TOKEN = "instance_identity/v1/token" 
META_URL_CERT = "instance_identity/v1/certificates"
META_URL_INSTANCE = "metadata/v1/instance"
META_VERSION = "2022-03-01"
META_FLAVOUR = "ibm"
META_TIMEOUT = 20
META_CERTIFICATE_DURATION_MIN = 300
META_CERTIFICATE_DURATION_MAX = 3600


class JsonRequest(MountHelperBase):
    def __init__(self):
        self.init_request(None)

    def init_request(self, url, timeout=0):
        self.headers = {}
        self.params = {}
        self.url = url
        self.context = None
        self.data = None
        self.response = {}
        self.timeout = timeout

    def set_data(self, data):
        self.data = data

    def add_header(self, name, value):
        self.headers[name] = value

    def add_param(self, name, value):
        self.params[name] = value

    # user friendly error message
    def log_user_error(self, usr_msg, err_msg):
        self.LogUser("MetadataService: " + usr_msg)
        self.LogDebug("MetadataServiceException: " + err_msg)

    def create_ssl_context(self):
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        self.context = ctx

    # wrap urlopen to make it easier to test

    def do_urlopen(self, req):
        return urlopen(req, timeout=self.timeout, context=self.context)

    def set_resp_json(self, resp):
        try:
            data = resp.read()
            self.response = json.loads(decode(data))
            return self.response is not None
        except Exception as ex:
            msg = "Problem Decoding JSON reponse(%s)" % (str(ex))
            self.log_user_error("problem reading response data", msg)
        return False

    def do_request(self, method):
        assert not is_empty(self.url)

        try:
            url = self.url
            if len(self.params) > 0:
                url += "?" + urlencode(self.params)

            data = self.data.encode('utf-8') if self.data else None

            self.LogDebug("Url: " + url)
            req = Request(url=url, data=data,
                          headers=self.headers, method=method)
            resp = self.do_urlopen(req)
            return self.set_resp_json(resp)
        except socket.timeout:
            self.log_user_error("Request Timeout Error", "Socket Timeout")
        except HTTPError as errh:
            msg = "Problem accessing (%s) - Status:%d Reason:%s Headers(%s)" % \
                (url, errh.code, errh.reason, errh.headers)
            self.log_user_error("Http Error", msg)
        except URLError as erru:
            msg = "Problem accessing (%s) - Reason:%s" % (url, erru.reason)
            self.log_user_error("Url Error", msg)
        except:
            self.log_user_error("UnknownException", "n/a")
        return False

    def get_out(self, name):
        ndx = -1
        parts = name.split(":")
        if len(parts) == 2:
            name = parts[0]
            ndx = int(parts[1])

        if name not in self.response:
            self.LogError("Field missing from response: " + name)
            return None

        if ndx >= 0:
            if len(self.response[name]) < (ndx+1):
                self.LogError("Index out of range: " + name)
                return None

            return trim(self.response[name][ndx])
        return trim(self.response[name])

    def post(self):
        return self.do_request("POST")

    def put(self):
        return self.do_request("PUT")

    def get(self):
        return self.do_request("GET")


class Metadata(CertificateHandler):
    def __init__(self):
        super().__init__()

        self.token = None
        self.instance_id = None
        self.private_key = None
        self.csr = None
        self.cert = None
        self.cert_int_ca = None
        self.created_at = None
        self.expires_at = None
        self.port = None

    def is_metadata_service_available(self):
        if self.is_port_available(META_IP, META_PORT_HTTP):
            return True
        return self.is_port_available(META_IP, META_PORT_HTTPS)

    def is_port_available(self, ip, port):
        ret = False
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(1)  # Timeout in case of port not open
                s.connect((ip, port))
                s.close()
                self.port = port
                ret = True
        except:
            pass
        self.LogDebug("Connect %s:%s %s" %
                      (ip, port, "success" if ret else "failed"))
        return ret


    def new_request(self, url, token=None):
        use_ssl = self.port == META_PORT_HTTPS
        pfx = "https" if use_ssl else "http"
        url = "%s://%s/%s" % (pfx, META_IP,url)
        req = JsonRequest()
        req.init_request(url, META_TIMEOUT)
        if use_ssl:
            req.create_ssl_context()
        req.add_header('Accept', 'application/json')
        req.add_param("version", META_VERSION)
        if token:
            req.add_header("Authorization", "Bearer " + token)
        return req

    def get_token(self):
        req = self.new_request(META_URL_TOKEN)
        req.add_header("Metadata-Flavor", META_FLAVOUR)
        if not req.put():
            return False
        self.token = req.get_out("access_token")
        return not is_empty(self.token)

    def generate_certs(self):
        if not self.token or not self.csr:
            self.LogError("Token and csr must be set")
            return False

        cfgShare = ShareConfig(None)
        expires_in = cfgShare.get_certificate_duration()
        if (not expires_in or int(expires_in) < META_CERTIFICATE_DURATION_MIN
               or int(expires_in) > META_CERTIFICATE_DURATION_MAX):
            expires_in = str(META_CERTIFICATE_DURATION_MAX)

        req = self.new_request(META_URL_CERT, self.token)
        req.set_data('{"csr": "' + self.csr + '", "expires_in": ' + expires_in + '}')
        if not req.post():
            return False

        def get_cert(cert):
            if cert and self.load_cert(cert):
                return cert
            return None

        self.cert = get_cert(req.get_out("certificates:0"))
        self.cert_int_ca = get_cert(req.get_out("certificates:1"))
        if not self.cert or not self.cert_int_ca:
            return False

        self.created_at = req.get_out("created_at")
        self.expires_at = req.get_out("expires_at")

        return True

    def set_private_key(self, data):
        if self.load_private_key(data):
            self.private_key = data
            return True
        else:
            self.LogError("Could not load private key.")
        return False

    def new_private_key(self):
        private_key = self.generate_private_key()
        return self.set_private_key(private_key)

    def new_certificate_signing_request(self):
        self.csr = self.generate_csr(self.private_key)
        return not is_empty(self.csr)
