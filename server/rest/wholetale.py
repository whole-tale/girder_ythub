#!/usr/bin/env python
# -*- coding: utf-8 -*-
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from girder.api import access
from girder.api.describe import Description, describeRoute
from girder.api.rest import Resource

from ..constants import PluginSettings


class wholeTale(Resource):

    def __init__(self):
        super(wholeTale, self).__init__()
        self.resourceName = 'wholetale'

        self.route('GET', (), self.get_wholetale_url)
        self.route('POST', ('genkey',), self.generateRSAKey)

    @access.admin
    @describeRoute(
        Description('Generate wholetale\'s RSA key')
    )
    def generateRSAKey(self, params):
        rsa_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        )

        pubkey_pem = rsa_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode('utf8')
        privkey_pem = rsa_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption()
        ).decode('utf8')
        self.model('setting').set(PluginSettings.HUB_PUB_KEY, pubkey_pem)
        self.model('setting').set(PluginSettings.HUB_PRIV_KEY, privkey_pem)
        return {PluginSettings.HUB_PUB_KEY: pubkey_pem,
                PluginSettings.HUB_PRIV_KEY: privkey_pem}

    @access.public
    @describeRoute(
        Description('Return url for tmpnb hub.')
    )
    def get_wholetale_url(self, params):
        setting = self.model('setting')
        return {'url': setting.get(PluginSettings.TMPNB_URL),
                'pubkey': setting.get(PluginSettings.HUB_PUB_KEY)}
