import httmock
import json
import os
from girder.constants import AccessType
from tests import base
from .tests_helpers import \
    GOOD_REPO, GOOD_COMMIT, \
    mockOtherRequest, mockCommitRequest, mockReposRequest


def setUpModule():
    base.enabledPlugins.append('wholetale')
    base.startServer()


def tearDownModule():
    base.stopServer()


class RecipeTestCase(base.TestCase):

    def setUp(self):
        super(RecipeTestCase, self).setUp()

    def testGetLicenses(self):
        resp = self.request(
            path='/license', method='GET',
            type='application/json')
        print(resp.json)

        # Make sure that we support CC0
        is_supported = all(x for x in resp.json if (x['spdx'] == 'CCO-1.0'))
        self.assertTrue(is_supported)
        # Make sure that we support CC-BY
        is_supported = all(x for x in resp.json if (x['spdx'] == 'CC-BY-4.0'))
        self.assertTrue(is_supported)

    def tearDown(self):
        super(RecipeTestCase, self).tearDown()
