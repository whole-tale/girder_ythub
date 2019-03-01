from tests import base


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
        self.license = 'CCO'

    def testCreateBasicAttributes(self):
        # Test that the basic attributes are correct
        from server.lib.manifest import Manifest
        manifest_doc = Manifest(self.license)

        tale_id = '12345'
        title = 'Tale Title'
        description = 'Tale description'
        category = 'science'
        version = 4
        image = 'imageURL'
        created = ''

        tale = {
            '_id': tale_id,
            'title': title,
            'description': description,
            'category': category,
            'format': version,
            'illustration': image,
            'created': created

        }
        attributes = manifest_doc.create_basic_attributes(tale)
        self.assertEqual(attributes['schema:identifier'], tale_id)
        self.assertEqual(attributes['schema:name'], title)
        self.assertEqual(attributes['schema:description'], description)
        self.assertEqual(attributes['schema:category'], category)
        self.assertEqual(attributes['schema:version'], version)
        self.assertEqual(attributes['schema:image'], image)

    def testAddTaleCreator(self):
        from server.lib.manifest import Manifest

        first_name = self.user['firstName']
        last_name = self.user['lastName']
        email = 'email@anemailserver'
        tale_author = first_name + ' ' + last_name
        tale = {
            'authors': tale_author,
            'creatorId': self.user['_id']
        }
        manifest_doc = Manifest(self.license)
        manifest_doc.add_tale_creator(tale, self.user)
        manifest_creator = manifest_doc.manifest['createdBy']
        self.assertEqual(manifest_creator['schema:givenName'], self.user['firstName'])
        self.assertEqual(manifest_creator['schema:familyName'], self.user['lastName'])
        self.assertEqual(manifest_creator['schema:email'], self.user['email'])
        self.assertEqual(manifest_creator['@id'], tale['authors'])

    def testCreateContext(self):
        # Rather than check the contents of the context (subject to change), check that we
        # get a dict back
        from server.lib.manifest import Manifest

        manifest_doc = Manifest(self.license)
        context = manifest_doc.create_context()
        self.assertEqual(type(context), type(dict()))

    def testCleanWorkspacePath(self):
        # Test that the Tale ID is removed
        from server.lib.manifest import clean_workspace_path
        path = 'mydatapath/moredata/'

        tale_id = '123456'
        res = clean_workspace_path(tale_id, path + tale_id+'/')
        self.assertEqual(res, path)

    def tearDown(self):
        self.model('user').remove(self.user)
        self.model('user').remove(self.admin)
        super(ManifestTestCase, self).tearDown()
