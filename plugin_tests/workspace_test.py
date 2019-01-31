from bson import ObjectId
from tests import base


def setUpModule():
    base.enabledPlugins.append('wholetale')
    base.startServer()


def tearDownModule():
    base.stopServer()


class WorkspaceTestCase(base.TestCase):
    def setUp(self):
        users = (
            {
                'email': 'root@dev.null',
                'login': 'admin',
                'firstName': 'Root',
                'lastName': 'van Klompf',
                'password': 'secret',
            },
            {
                'email': 'joe@dev.null',
                'login': 'joeregular',
                'firstName': 'Joe',
                'lastName': 'Regular',
                'password': 'secret',
            },
        )
        self.admin, self.user = [
            self.model('user').createUser(**user) for user in users
        ]
        self.tale_one = self.model('tale', 'wholetale').createTale(
            {'_id': ObjectId()}, [], creator=self.user, title='Tale One', public=True
        )
        self.tale_two = self.model('tale', 'wholetale').createTale(
            {'_id': ObjectId()}, [], creator=self.admin, title='Tale Two', public=True
        )

    def testLookup(self):
        resp = self.request(path='/workspace', method='GET', user=self.user)
        self.assertStatus(resp, 200)
        self.assertEqual(resp.json[0]['lowerName'], self.tale_one['title'].lower())
        self.assertEqual(resp.json[1]['name'], self.tale_two['title'])
        workspace_two = resp.json[1]

        resp = self.request(
            path='/workspace/{_id}'.format(**self.tale_two),
            method='GET',
            user=self.user,
        )
        self.assertStatus(resp, 200)
        self.assertEqual(resp.json, workspace_two)

    def tearDown(self):
        for user in (self.user, self.admin):
            self.model('user').remove(user)
        for tale in (self.tale_one, self.tale_two):
            self.model('tale', 'wholetale').remove(tale)
