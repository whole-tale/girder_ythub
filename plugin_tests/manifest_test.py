from tests import base
from bson import ObjectId


def setUpModule():
    base.enabledPlugins.append('wholetale')
    base.startServer()


def tearDownModule():
    base.stopServer()


class ManifestTestCase(base.TestCase):

    def setUp(self):
        super(ManifestTestCase, self).setUp()
        self.users = ({
            'email': 'root@dev.null',
            'login': 'admin',
            'firstName': 'Root',
            'lastName': 'van Klompf',
            'password': 'secret',
            'admin': True
        }, {
            'email': 'joe@dev.null',
            'login': 'joeregular',
            'firstName': 'Joe',
            'lastName': 'Regular',
            'password': 'secret'
        })
        self.admin, self.user = [self.model('user').createUser(**user)
                                 for user in self.users]

        data_collection = self.model('collection').createCollection('WholeTale Catalog', self.user)
        workspace_collection = self.model('collection').createCollection('WholeTale Workspaces', self.user)
        self.workspace_folder = self.model('folder').createFolder(
            workspace_collection, 'WholeTale Workspaces', parentType='collection')
        self.data_folder = self.model('folder').createFolder(
            data_collection, 'Data', parentType='collection')
        self.data_folder2 = self.model('folder').createFolder(
            data_collection, 'WholeTale Catalog', parentType='collection')

        self.workspace_top_item1 = self.model('item').createItem('workspace file1.csv',
                                                                 self.user,
                                                                 self.workspace_folder)
        self.workspace_top_item2 = self.model('item').createItem('ws_item2',
                                                                 self.user,
                                                                 self.workspace_folder)

        self.data_top_item1 = self.model('item').createItem('data file1.csv',
                                                            self.user,
                                                            self.data_folder)
        self.data_top_item2 = self.model('item').createItem('data_item2',
                                                            self.user,
                                                            self.data_folder)

        self.floating_item = self.model('item').createItem('data_item.csv',
                                                            self.user,
                                                            self.data_folder2)

        # Add meta sections to dataSet items
        self.model('item').setMetadata(self.data_top_item1, {'identifier': '1234'})
        self.model('item').setMetadata(self.data_top_item2, {'identifier': '4321'})
        self.model('item').setMetadata(self.floating_item, {'identifier': '4321a'})
        self.model('folder').setMetadata(self.data_folder, {'identifier': '123456',
                                                            'provider': 'DataONE'})
        self.model('folder').setMetadata(self.data_folder2, {'identifier': '1234516',
                                                            'provider': 'Globus'})

        # Create files for each item
        assetstore = {'_id': 0}
        self.ws_fl1 = self.model('file').createFile(self.user,
                                                    self.workspace_top_item1,
                                                    'workspace file1.csv',
                                                    7,
                                                    assetstore)
        self.ws_fl2 = self.model('file').createFile(self.user,
                                                    self.workspace_top_item2,
                                                    'workspace file2.csv',
                                                    7,
                                                    assetstore)

        self.fake_url1 = 'http:Fake_URI'
        self.fake_url2 = 'http:Fake_URI2'
        self.fake_url3 = 'http:Fake_URI3'

        self.data_fl1 = self.model('file').createLinkFile('data file1.csv',
                                                          self.data_top_item1,
                                                          'item',
                                                          self.fake_url1,
                                                          self.user)

        self.data_fl2 = self.model('file').createLinkFile('data file2.csv',
                                                          self.data_top_item2,
                                                          'item',
                                                          self.fake_url2,
                                                          self.user)

        self.floating_file = self.model('file').createLinkFile('data file3.csv',
                                                          self.floating_item,
                                                          'item',
                                                          self.fake_url3,
                                                          self.user)

        # Tale map of values to check against in tests
        self.tale_info = {'_id': ObjectId(),
                          'name': 'Main Tale',
                          'description': 'Tale Desc',
                          'authors': self.user['firstName'] + ' ' + self.user['lastName'],
                          'creator': self.user,
                          'public': True,
                          'data': [{'itemId': self.data_folder['_id'],
                                    '_mountPath': self.data_folder['name'],
                                    '_modelType': 'folder'},
                                   {'itemId': self.floating_item['_id'],
                                    '_mountPath': self.floating_item['name'],
                                    '_modelType': 'item'}],
                          'illustration': 'linkToImage',
                          'workspaceId': self.workspace_folder['_id']}

        self.tale = self.model('tale', 'wholetale').createTale(
            {'_id': self.tale_info['_id']},
            data=self.tale_info['data'],
            creator=self.tale_info['creator'],
            title=self.tale_info['name'],
            public=self.tale_info['public'],
            description=self.tale_info['description'],
            authors=self.tale_info['authors']
        )

        self.tale2 = self.model('tale', 'wholetale').createTale(
            {'_id': self.tale_info['_id']},
            data=[],
            creator=self.tale_info['creator'],
            title=self.tale_info['name'],
            public=self.tale_info['public'],
            description=self.tale_info['description'],
            authors=self.tale_info['authors']
        )

    def testCreateBasicAttributes(self):
        # Test that the basic attributes are correct
        from server.lib.manifest import Manifest
        manifest_doc = Manifest(self.tale, self.user)

        attributes = manifest_doc.create_basic_attributes()
        self.assertEqual(attributes['schema:identifier'], str(self.tale['_id']))
        self.assertEqual(attributes['schema:name'], self.tale['title'])
        self.assertEqual(attributes['schema:description'], self.tale['description'])
        self.assertEqual(attributes['schema:category'], self.tale['category'])
        self.assertEqual(attributes['schema:version'], self.tale['format'])
        self.assertEqual(attributes['schema:image'], self.tale['illustration'])

    def testAddTaleCreator(self):
        from server.lib.manifest import Manifest

        manifest_doc = Manifest(self.tale, self.user)
        manifest_creator = manifest_doc.manifest['createdBy']
        self.assertEqual(manifest_creator['schema:givenName'], self.user['firstName'])
        self.assertEqual(manifest_creator['schema:familyName'], self.user['lastName'])
        self.assertEqual(manifest_creator['schema:email'], self.user['email'])
        self.assertEqual(manifest_creator['@id'], self.tale['authors'])

    def testCreateContext(self):
        # Rather than check the contents of the context (subject to change), check that we
        # get a dict back
        from server.lib.manifest import Manifest

        manifest_doc = Manifest(self.tale, self.user)
        context = manifest_doc.create_context()
        self.assertEqual(type(context), type(dict()))

    def testCleanWorkspacePath(self):
        # Test that the Tale ID is removed
        from server.lib.manifest import clean_workspace_path
        path = 'mydatapath/moredata/'

        tale_id = '123456'
        res = clean_workspace_path(tale_id, path + tale_id+'/')
        self.assertEqual(res, path)

    def testCreateAggregationRecord(self):
        from server.lib.manifest import Manifest
        # Test without a bundle
        manifest_doc = Manifest(self.tale, self.user)
        uri = 'doi:xx.xxxx.1234'
        agg = manifest_doc.create_aggregation_record(uri)
        self.assertEqual(agg['uri'], uri)

        # Test with a bundle
        folder_name = 'research_data'
        filename = 'data.csv'
        bundle = {'folder': folder_name,
                  'filename': filename}

        agg = manifest_doc.create_aggregation_record(uri, bundle)
        self.assertEqual(agg['uri'], uri)
        self.assertEqual(agg['bundledAs']['folder'], folder_name)
        self.assertEqual(agg['bundledAs']['filename'], filename)

        # Test with a parent dataset
        parent_dataset = 'urn:uuid:100.99.xx'
        agg = manifest_doc.create_aggregation_record(uri, bundle, parent_dataset)
        self.assertEqual(agg['schema:isPartOf'], parent_dataset)

    def testGetFolderIdentifier(self):
        from server.lib.manifest import get_folder_identifier

        folder_identifier = get_folder_identifier(self.data_folder['_id'],
                                                  self.user)
        self.assertEqual(folder_identifier, self.data_folder['meta']['identifier'])

    def testWorkspace(self):
        from server.lib.manifest import Manifest
        # Test that all of the files in the workspace have aggregation records

        self.tale['workspaceId'] = self.workspace_folder['_id']
        manifest_doc = Manifest(self.tale, self.user)
        aggregates_section = manifest_doc.manifest['aggregates']

        # Search for workspace file1.csv
        expected_path = '../workspace/' +\
                        self.workspace_folder['name'] + '/' + \
                        self.workspace_top_item1['name']

        file_check = any(x for x in aggregates_section if (x['uri'] == expected_path))
        self.assertTrue(file_check)

        # Search for workspace file2.csv
        expected_path = '../workspace/' +\
                        self.workspace_folder['name'] + '/' + \
                        self.workspace_top_item2['name'] + '/' +\
                        self.ws_fl2['name']

        file_check = any(x for x in aggregates_section if (x['uri'] == expected_path))
        self.assertTrue(file_check)

    def testDataSet(self):
        from server.lib.manifest import Manifest
        # Test that all of the files in the dataSet are added
        manifest_doc = Manifest(self.tale, self.user)

        aggregates_section = manifest_doc.manifest['aggregates']

        file_check = (x for x in aggregates_section if (x['uri'] == self.fake_url1))
        for record in file_check:
            self.assertEqual(record['uri'], self.fake_url1)
            self.assertEqual(record['schema:isPartOf'], self.data_folder['meta']['identifier'])
            self.assertEqual(record['bundledAs']['filename'], self.data_fl1['name'])

        file_check = (x for x in aggregates_section if (x['uri'] == self.fake_url2))
        for record in file_check:
            self.assertEqual(record['uri'], self.fake_url2)
            self.assertEqual(record['schema:isPartOf'], self.data_folder['meta']['identifier'])
            self.assertEqual(record['bundledAs']['filename'], self.data_fl2['name'])

        # Check the datasets
        datasets = manifest_doc.manifest['Datasets']
        file_check = all(x for x in datasets if (x['publisher']['legalName'] == 'DataONE'))
        self.assertTrue(file_check)

        file_check = all(x for x in datasets if (x['publisher']['legalName'] == 'Globus'))
        self.assertTrue(file_check)

    def testItems(self):
        from server.lib.manifest import Manifest
        # Test that a manifest can be created from a list of items
        self.assertEqual(True, True)
        item_ids = [self.floating_item['_id'], self.workspace_top_item1['_id']]

        manifest_doc = Manifest(self.tale, self.user, item_ids)
        aggregates_section = manifest_doc.manifest['aggregates']
        expected_path = '../workspace/' + \
                        self.workspace_folder['name'] + '/' + \
                        self.workspace_top_item1['name']

        # Check the workspace file
        file_check = all(x for x in aggregates_section if (x['uri'] == expected_path))
        self.assertTrue(file_check)

        # Check the data item
        file_check = (x for x in aggregates_section if (x['uri'] == self.fake_url3))
        self.assertTrue(file_check)

        # Check the dataset
        datasets = manifest_doc.manifest['Datasets']
        file_check = all(x for x in datasets if (x['publisher']['legalName'] == 'DataONE'))
        self.assertTrue(file_check)

    def tearDown(self):
        self.model('user').remove(self.user)
        self.model('user').remove(self.admin)
        super(ManifestTestCase, self).tearDown()
