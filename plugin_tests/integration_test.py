#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import vcr
from tests import base
from urllib.parse import urlparse, parse_qs

DATA_PATH = os.path.join(
    os.path.dirname(os.environ['GIRDER_TEST_DATA_PREFIX']),
    'data_src',
    'plugins',
    'wholetale',
)


def setUpModule():
    base.enabledPlugins.append('wholetale')
    base.startServer()


def tearDownModule():
    base.stopServer()


class IntegrationTestCase(base.TestCase):
    @vcr.use_cassette(os.path.join(DATA_PATH, 'dataverse_integration.txt'))
    def testDataverseIntegration(self):
        resp = self.request(
            '/integration/dataverse',
            method='GET',
            params={'fileId': 'blah', 'siteUrl': 'https://dataverse.someplace'},
        )
        self.assertStatus(resp, 400)
        self.assertEqual(
            resp.json, {'message': 'Invalid fileId (should be integer)', 'type': 'rest'}
        )

        resp = self.request(
            '/integration/dataverse',
            method='GET',
            params={'fileId': '1234', 'siteUrl': 'definitely not a URL'},
        )
        self.assertStatus(resp, 400)
        self.assertEqual(
            resp.json, {'message': 'Not a valid URL: siteUrl', 'type': 'rest'}
        )

        resp = self.request(
            '/integration/dataverse',
            method='GET',
            params={
                'fileId': '3020113',
                'siteUrl': 'https://dataverse.harvard.edu',
                'fullDataset': False,
            },
        )
        self.assertStatus(resp, 303)
        self.assertEqual(
            parse_qs(urlparse(resp.headers['Location']).query),
            {
                'uri': ['https://dataverse.harvard.edu/api/access/datafile/3020113'],
                'name': [
                    'Replication Data for: '
                    'The Economic Consequences of Partisanship in a Polarized Era'
                ],
                'asTale': ['True'],
            },
        )

        resp = self.request(
            '/integration/dataverse',
            method='GET',
            params={
                'fileId': '3020113',
                'siteUrl': 'https://dataverse.harvard.edu',
                'fullDataset': True,
            },
        )
        self.assertStatus(resp, 303)
        self.assertEqual(
            parse_qs(urlparse(resp.headers['Location']).query),
            {
                'uri': [
                    'https://dataverse.harvard.edu/dataset.xhtml'
                    '?persistentId=doi:10.7910/DVN/R3GZZW'
                ],
                'name': [
                    'Replication Data for: '
                    'The Economic Consequences of Partisanship in a Polarized Era'
                ],
                'asTale': ['True'],
            },
        )

    def testDataoneIntegration(self):
        resp = self.request(
            '/integration/dataone',
            method='GET',
            params={
                'uri': 'urn:uuid:12345.6789',
                'title': 'dataset title',
                'environment': 'rstudio',
            },
        )
        self.assertStatus(resp, 303)
        query = parse_qs(urlparse(resp.headers['Location']).query)
        self.assertEqual(query['name'][0], 'dataset title')
        self.assertEqual(query['uri'][0], 'urn:uuid:12345.6789')
        self.assertEqual(query['environment'][0], 'rstudio')
