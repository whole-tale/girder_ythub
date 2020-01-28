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
                'https://doi.org/10.7910/DVN/RLMYMR/WNKD3W',
                'https://dataverse.harvard.edu/api/access/datafile/3040230'
            ])}
        )
        self.assertStatus(resp, 200)
        self.assertEqual(resp.json, [
            {
                "dataId": "https://dataverse.harvard.edu/dataset.xhtml"
                          "?persistentId=doi:10.7910/DVN/RLMYMR",
                "doi": "doi:10.7910/DVN/RLMYMR",
                "name": "Karnataka Diet Diversity and Food Security for "
                        "Agricultural Biodiversity Assessment",
                "repository": "Dataverse",
                "size": 495885,
                "tale": False,
            },
            {
                "dataId": "https://dataverse.harvard.edu/file.xhtml"
                          "?persistentId=doi:10.7910/DVN/RLMYMR/WNKD3W",
                "doi": "doi:10.7910/DVN/RLMYMR",
                "name": "Karnataka Diet Diversity and Food Security for "
                        "Agricultural Biodiversity Assessment",
                "repository": "Dataverse",
                "size": 2321,
                "tale": False,
            },
            {
                "dataId": "https://dataverse.harvard.edu/api/access/datafile/3040230",
                "doi": "doi:10.7910/DVN/TJCLKP",
                "name": "Open Source at Harvard",
                "repository": "Dataverse",
                "size": 12025,
                "tale": False,
            }
        ])

        resp = self.request(
            path='/repository/listFiles', method='GET', user=self.user,
            params={'dataId': json.dumps([
                'https://doi.org/10.7910/DVN/RLMYMR',
                'https://doi.org/10.7910/DVN/RLMYMR/WNKD3W',
                'https://dataverse.harvard.edu/api/access/datafile/3040230'
            ])}
        )
        self.assertStatus(resp, 200)
        self.assertEqual(resp.json, [
            {
                "Karnataka Diet Diversity and Food Security for "
                "Agricultural Biodiversity Assessment": {
                    "fileList": [
                        {"Karnataka_DDFS_Data-1.tab": {"size": 2408}},
                        {"Karnataka_DDFS_Data-1.xlsx": {"size": 700840}},
                        {"Karnataka_DDFS_Questionnaire.pdf": {"size": 493564}}
                    ]
                }
            },
            {
                "Karnataka Diet Diversity and Food Security for "
                "Agricultural Biodiversity Assessment": {
                    "fileList": [
                        {"Karnataka_DDFS_Data-1.tab": {"size": 2408}},
                        {"Karnataka_DDFS_Data-1.xlsx": {"size": 700840}}
                    ]
                }
            },
            {
                "Open Source at Harvard": {
                    "fileList": [
                        {"2017-07-31.csv": {"size": 11684}},
                        {"2017-07-31.tab": {"size": 12100}}
                    ]
                }
            }
        ])

    def testConfigValidators(self):
        from girder.plugins.wholetale.constants import PluginSettings, SettingDefault
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

        resp = self.request(
            '/system/setting', user=self.admin, method='PUT',
            params={'key': PluginSettings.DATAVERSE_URL,
                    'value': ''})
        self.assertStatusOk(resp)
        resp = self.request(
            '/system/setting', user=self.admin, method='GET',
            params={'key': PluginSettings.DATAVERSE_URL})
        self.assertStatusOk(resp)
        self.assertEqual(
            resp.body[0].decode(),
            '"{}"'.format(SettingDefault.defaults[PluginSettings.DATAVERSE_URL]))

    @vcr.use_cassette(os.path.join(DATA_PATH, 'dataverse_single.txt'))
    def testSingleDataverseInstance(self):
        from girder.plugins.wholetale.constants import PluginSettings, SettingDefault
        resp = self.request('/system/setting', user=self.admin, method='PUT',
                            params={'key': PluginSettings.DATAVERSE_URL,
                                    'value': 'https://demo.dataverse.org/'})
        self.assertStatusOk(resp)

        resp = self.request(
            path='/repository/lookup', method='GET', user=self.user,
            params={'dataId': json.dumps([
                'https://demo.dataverse.org/api/access/datafile/300662'
            ])}
        )
        self.assertStatus(resp, 200)
        self.assertEqual(resp.json, [
            {
                "dataId": "https://demo.dataverse.org/api/access/datafile/300662",
                "doi": "doi:10.5072/FK2/N7YHEY",
                "name": "Variable-level metadata always accessible",
                "repository": "Dataverse",
                "size": 36843,
                "tale": False,
            }
        ])

        resp = self.request(
            path='/repository/listFiles', method='GET', user=self.user,
            params={'dataId': json.dumps([
                'https://demo.dataverse.org/api/access/datafile/300662'
            ])}
        )
        self.assertStatus(resp, 200)
        self.assertEqual(resp.json, [
            {
                "Variable-level metadata always accessible": {
                    "fileList": [
                        {"citation.tab": {"size": 36920}},
                        {"citation.xlsx": {"size": 26465}}
                    ]
                }
            }
        ])

        resp = self.request(
            '/system/setting', user=self.admin, method='PUT',
            params={'key': PluginSettings.DATAVERSE_URL,
                    'value': SettingDefault.defaults[PluginSettings.DATAVERSE_URL]})
        self.assertStatusOk(resp)

    def testExtraHosts(self):
        from girder.plugins.wholetale.constants import PluginSettings, SettingDefault
        resp = self.request('/system/setting', user=self.admin, method='PUT',
                            params={'key': PluginSettings.DATAVERSE_EXTRA_HOSTS,
                                    'value': 'https://dataverse.org/'})
        self.assertStatus(resp, 400)
        self.assertEqual(resp.json, {
            'field': 'value',
            'type': 'validation',
            'message': 'Dataverse extra hosts setting must be a list.'
        })

        resp = self.request('/system/setting', user=self.admin, method='PUT',
                            params={'key': PluginSettings.DATAVERSE_EXTRA_HOSTS,
                                    'value': json.dumps(['not a url'])})
        self.assertStatus(resp, 400)
        self.assertEqual(resp.json, {
            'field': 'value',
            'type': 'validation',
            'message': 'Invalid URL in Dataverse extra hosts'
        })

        # defaults
        resp = self.request(
            '/system/setting', user=self.admin, method='PUT',
            params={'key': PluginSettings.DATAVERSE_EXTRA_HOSTS,
                    'value': ''})
        self.assertStatusOk(resp)
        resp = self.request(
            '/system/setting', user=self.admin, method='GET',
            params={'key': PluginSettings.DATAVERSE_EXTRA_HOSTS})
        self.assertStatusOk(resp)
        self.assertEqual(
            resp.body[0].decode(),
            str(SettingDefault.defaults[PluginSettings.DATAVERSE_EXTRA_HOSTS]))

        resp = self.request(
            '/system/setting', user=self.admin, method='PUT',
            params={'list': json.dumps([
                {
                    'key': PluginSettings.DATAVERSE_EXTRA_HOSTS,
                    'value': ['https://random.d.org', 'https://random2.d.org']
                },
                {
                    'key': PluginSettings.DATAVERSE_URL,
                    'value': 'https://demo.dataverse.org'
                }
            ])}
        )
        self.assertStatusOk(resp)
        from girder.plugins.wholetale.lib.dataverse.provider import DataverseImportProvider
        self.assertEqual(
            '^https://demo.dataverse.org|https://random.d.org|https://random2.d.org.*$',
            DataverseImportProvider().regex.pattern
        )
        resp = self.request(
            '/system/setting', user=self.admin, method='PUT',
            params={'key': PluginSettings.DATAVERSE_URL,
                    'value': SettingDefault.defaults[PluginSettings.DATAVERSE_URL]})

    @vcr.use_cassette(os.path.join(DATA_PATH, 'dataverse_hierarchy.txt'))
    def testDatasetWithHierarchy(self):
        from girder.plugins.wholetale.constants import PluginSettings, SettingDefault
        resp = self.request(
            '/system/setting', user=self.admin, method='PUT',
            params={'list': json.dumps([
                {
                    'key': PluginSettings.DATAVERSE_URL,
                    'value': 'https://dev2.dataverse.org'
                },
            ])}
        )
        self.assertStatusOk(resp)
        resp = self.request(
            path='/repository/listFiles', method='GET', user=self.user,
            params={'dataId': json.dumps([
                (
                    'https://dev2.dataverse.org/dataset.xhtml?'
                    'persistentId=doi:10.5072/FK2/NYNHAM'
                )
            ])}
        )
        self.assertStatus(resp, 200)
        root_folder = 'dataverse-irc-metrics-8f0b5b505de7730ebd9d57439952542a66a6bae0'
        self.assertEqual(
            resp.json[0]['Dataverse IRC Metrics'][root_folder]['data'],
            {'fileList': [{'irclog.tsv': {'size': 9694487}}]}
        )

        resp = self.request(
            '/system/setting', user=self.admin, method='PUT',
            params={'key': PluginSettings.DATAVERSE_URL,
                    'value': SettingDefault.defaults[PluginSettings.DATAVERSE_URL]})

    def tearDown(self):
        self.model('user').remove(self.user)
        self.model('user').remove(self.admin)
