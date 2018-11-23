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


class DataverseHarversterTestCase(base.TestCase):

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
                'https://doi.org/10.7910/DVN/RLMYMR',
                'https://doi.org/10.7910/DVN/RLMYMR/WNKD3W'
            ])}
        )
        self.assertStatus(resp, 200)
        self.assertEqual(resp.json, [
	    {
		"dataId": "https://dataverse.harvard.edu/citation?persistentId=doi:10.7910/DVN/RLMYMR",
		"doi": "10.7910/DVN/RLMYMR",
		"name": "Karnataka Diet Diversity and Food Security for Agricultural Biodiversity Assessment",
		"repository": "Dataverse",
		"size": 495885
	    },
	    {
		"dataId": "https://dataverse.harvard.edu/file.xhtml?persistentId=doi:10.7910/DVN/RLMYMR/WNKD3W",
		"doi": "10.7910/DVN/RLMYMR",
		"name": "Karnataka Diet Diversity and Food Security for Agricultural Biodiversity Assessment",
		"repository": "Dataverse",
		"size": 2321
	    }
        ])

        resp = self.request(
            path='/repository/listFiles', method='GET', user=self.user,
            params={'dataId': json.dumps([
                'https://doi.org/10.7910/DVN/RLMYMR',
                'https://doi.org/10.7910/DVN/RLMYMR/WNKD3W'
            ])}
        )
        self.assertStatus(resp, 200)
        self.assertEqual(resp.json, [
            {
                "Karnataka Diet Diversity and Food Security for "
                "Agricultural Biodiversity Assessment": {
                    "fileList": [
                        {"Karnataka_DD&FS_Data-1.tab": {"size": 2408}},
                        {"Karnataka_DD&FS_Data-1.xlsx": {"size": 700840}},
                        {"Karnataka_DD&FS_Questionnaire.pdf": {"size": 493564}}
                    ]
                }
            },
            {
                "Karnataka Diet Diversity and Food Security for "
                "Agricultural Biodiversity Assessment": {
                    "fileList": [
                        {"Karnataka_DD&FS_Data-1.tab": {"size": 2408}},
                        {"Karnataka_DD&FS_Data-1.xlsx": {"size": 700840}}
                    ]
                }
            }
        ])

    def testConfigValidators(self):
        from girder.plugins.wholetale.constants import PluginSettings, SettingDefault
        resp = self.request('/system/setting', user=self.admin, method='PUT',
                            params={'key': PluginSettings.DATAVERSE_URL,
                                    'value': ''})
        self.assertStatus(resp, 400)
        self.assertEqual(resp.json, {
            'field': 'value',
            'type': 'validation',
            'message': 'Dataverse Instances list URL must not be empty.'
        })

        resp = self.request('/system/setting', user=self.admin, method='PUT',
                            params={'key': PluginSettings.DATAVERSE_URL,
                                    'value': 'random_string'})
        self.assertStatus(resp, 400)
        self.assertEqual(resp.json, {
            'field': 'value',
            'type': 'validation',
            'message': 'Invalid Dataverse URL'
        })

        resp = self.request(
            '/system/setting', user=self.admin, method='PUT',
            params={'key': PluginSettings.DATAVERSE_URL,
                    'value': SettingDefault.defaults[PluginSettings.DATAVERSE_URL]})
        self.assertStatusOk(resp)

    def tearDown(self):
        self.model('user').remove(self.user)
        self.model('user').remove(self.admin)
