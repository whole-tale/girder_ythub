#!/usr/bin/env python
# -*- coding: utf-8 -*-
from tests import base


def setUpModule():
    base.enabledPlugins.append('wholetale')
    base.startServer()


def tearDownModule():
    base.stopServer()


class IntegrationTestCase(base.TestCase):

    def testDataverseIntegration(self):
        resp = self.request(
            '/integration/dataverse', method='GET',
            params={'fileId': 'blah', 'siteUrl': 'https://dataverse.someplace'})
        self.assertStatus(resp, 400)
        self.assertEqual(resp.json, {
            'message': 'Invalid fileId (should be integer)',
            'type': 'rest'
        })

        resp = self.request(
            '/integration/dataverse', method='GET',
            params={'fileId': '1234', 'siteUrl': 'definitely not a URL'})
        self.assertStatus(resp, 400)
        self.assertEqual(resp.json, {
            'message': 'Not a valid URL: siteUrl',
            'type': 'rest'
        })

        resp = self.request(
            '/integration/dataverse', method='GET',
            params={'fileId': '1234', 'siteUrl': 'https://dataverse.someplace'})
        self.assertStatus(resp, 303)
        self.assertEqual(
            resp.headers['Location'],
            'https://dashboard.wholetale.org/compose?uri='
            'https%3A%2F%2Fdataverse.someplace%2Fapi%2Faccess%2Fdatafile%2F1234'
        )

    def testDataoneIntegration(self):
        resp = self.request(
            '/integration/dataone', method='GET',
            params={'uri': 'urn:uuid:12345.6789',
                    'title': 'dataset title',
                    'environment': 'rstudio'})
        self.assertStatus(resp, 303)
        self.assertEqual(
            resp.headers['Location'],
            'https://dashboard.wholetale.org/compose?environment=rstudio'
            '%26name%3Ddataset%2Btitle%26uri=urn%253Auuid%253A12345.6789'
        )
