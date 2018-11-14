import json
import os
import vcr
from tests import base


DATA_PATH = os.path.join(
    os.path.dirname(os.environ['GIRDER_TEST_DATA_PREFIX']),
    'data_src', 'plugins', 'wholetale'
)


def setUpModule():
    base.enabledPlugins.append('wholetale')
    base.startServer()


def tearDownModule():
    base.stopServer()


class DataONEHarversterTestCase(base.TestCase):

    def setUp(self):
        users = ({
            'email': 'root@dev.null',
            'login': 'admin',
            'firstName': 'Root',
            'lastName': 'van Klompf',
            'password': 'secret'
        }, {
            'email': 'joe@dev.null',
            'login': 'joeregular',
            'firstName': 'Joe',
            'lastName': 'Regular',
            'password': 'secret'
        })
        self.admin, self.user = [self.model('user').createUser(**user)
                                 for user in users]

    @vcr.use_cassette(os.path.join(DATA_PATH, 'dataverse_lookup.txt'))
    def testLookup(self):
        resp = self.request(
            path='/repository/lookup', method='GET', user=self.user,
            params={'dataId': json.dumps([
                'https://doi.org/10.7910/DVN/TJCLKP',
                'https://doi.org/10.7910/DVN/TJCLKP/JKTORG'
            ])}
        )
        self.assertStatus(resp, 200)
        self.assertEqual(resp.json, [
            {
                "dataId": "https://dataverse.harvard.edu/citation?"
                          "persistentId=doi:10.7910/DVN/TJCLKP",
                "doi": "10.7910/DVN/TJCLKP",
                "name": "Open Source at Harvard",
                "repository": "Dataverse",
                "size": 518379
            },
            {
                "dataId": "https://dataverse.harvard.edu/file.xhtml?"
                          "persistentId=doi:10.7910/DVN/TJCLKP/JKTORG",
                "doi": "10.7910/DVN/TJCLKP/JKTORG",
                "name": "Open Source at Harvard",
                "repository": "Dataverse",
                "size": 12100
            }
        ])

        resp = self.request(
            path='/repository/listFiles', method='GET', user=self.user,
            params={'dataId': json.dumps([
                'https://doi.org/10.7910/DVN/TJCLKP',
                'https://doi.org/10.7910/DVN/TJCLKP/JKTORG'
            ])}
        )
        self.assertStatus(resp, 200)
        fname = os.path.join(DATA_PATH, 'dataverse_listFiles.json')
        with open(fname, 'r') as fp:
            expected_result = json.load(fp)
        self.assertEqual(resp.json, expected_result)

    def tearDown(self):
        self.model('user').remove(self.user)
        self.model('user').remove(self.admin)
