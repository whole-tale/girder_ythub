
import httmock
import json
from tests import base
from .tests_helpers import \
    GOOD_REPO, GOOD_COMMIT, XPRA_REPO, XPRA_COMMIT, \
    mockOtherRequest, mockCommitRequest, mockReposRequest


def setUpModule():
    base.enabledPlugins.append('wholetale')
    base.startServer()


def tearDownModule():
    base.stopServer()


class TaleTestCase(base.TestCase):

    def setUp(self):
        super(TaleTestCase, self).setUp()
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
        with httmock.HTTMock(mockReposRequest, mockCommitRequest,
                             mockOtherRequest):
            self.recipe = self.model('recipe', 'wholetale').createRecipe(
                GOOD_COMMIT, 'https://github.com/' + GOOD_REPO,
                creator=self.user, public=True)
            recipe_admin = self.model('recipe', 'wholetale').createRecipe(
                XPRA_COMMIT, 'https://github.com/' + XPRA_REPO,
                creator=self.admin, public=True)
            self.image_admin = self.model('image', 'wholetale').createImage(
                recipe_admin, XPRA_REPO, name="xpra name", creator=self.admin,
                public=True)
        self.image = self.model('image', 'wholetale').createImage(
            self.recipe, GOOD_REPO, name="my name", creator=self.user,
            public=True)

    def testTaleFlow(self):
        resp = self.request(
            path='/tale', method='POST', user=self.user,
            type='application/json',
            body=json.dumps({'imageId': str(self.image['_id'])})
        )
        self.assertStatus(resp, 400)
        self.assertEqual(resp.json, {
            'message': ("Invalid JSON object for parameter tale: "
                        "'involatileData' "
                        "is a required property"),
            'type': 'rest'
        })

        # Grab the default user folders
        resp = self.request(
            path='/folder', method='GET', user=self.user, params={
                'parentType': 'user',
                'parentId': self.user['_id'],
                'sort': 'title',
                'sortdir': 1
            })
        privateFolder = resp.json[0]
        publicFolder = resp.json[1]

        resp = self.request(
            path='/folder', method='GET', user=self.admin, params={
                'parentType': 'user',
                'parentId': self.admin['_id'],
                'sort': 'title',
                'sortdir': 1
            })
        # adminPrivateFolder = resp.json[0]
        adminPublicFolder = resp.json[1]

        resp = self.request(
            path='/tale', method='POST', user=self.user,
            type='application/json',
            body=json.dumps({
                'imageId': str(self.image['_id']),
                'involatileData': [
                    {'type': 'folder', 'id': publicFolder['_id']}
                ]
            })
        )
        self.assertStatusOk(resp)
        tale = resp.json

        # Check that workspace was created

        # Check that data folder was created
        from girder.plugins.wholetale.constants import DATADIRS_NAME
        from girder.utility.path import getResourcePath
        from girder.models.folder import Folder
        sc = {
            '_id': tale['_id'],
            'cname': DATADIRS_NAME,
            'fname': DATADIRS_NAME
        }
        self.assertEqual(
            getResourcePath(
                'folder',
                Folder().load(tale['folderId'], user=self.user),
                user=self.admin),
            '/collection/{cname}/{fname}/{_id}'.format(**sc)
        )

        resp = self.request(
            path='/tale/{_id}'.format(**tale), method='PUT',
            type='application/json',
            user=self.user, body=json.dumps({
                'folderId': tale['folderId'],
                'involatileData': tale['involatileData'],
                'imageId': tale['imageId'],
                'title': 'new name',
                'description': 'new description',
                'config': {'memLimit': '2g'},
                'public': True,
                'published': False
            })
        )
        self.assertStatusOk(resp)
        self.assertEqual(resp.json['title'], 'new name')
        tale = resp.json

        resp = self.request(
            path='/tale', method='POST', user=self.user,
            type='application/json',
            body=json.dumps({
                'imageId': str(self.image['_id']),
                'involatileData': [
                    {'type': 'folder', 'id': privateFolder['_id']}
                ]
            })
        )
        self.assertStatusOk(resp)
        new_tale = resp.json

        resp = self.request(
            path='/tale', method='POST', user=self.admin,
            type='application/json',
            body=json.dumps({
                'imageId': str(self.image['_id']),
                'involatileData': [
                    {'type': 'folder', 'id': adminPublicFolder['_id']}
                ],
                'public': False
            })
        )
        self.assertStatusOk(resp)
        # admin_tale = resp.json

        resp = self.request(
            path='/tale', method='GET', user=self.admin,

            params={}
        )
        self.assertStatusOk(resp)
        self.assertEqual(len(resp.json), 3)

        resp = self.request(
            path='/tale', method='GET', user=self.user,
            params={'imageId': str(self.image['_id'])}
        )
        self.assertStatusOk(resp)
        self.assertEqual(len(resp.json), 2)
        self.assertEqual(set([_['_id'] for _ in resp.json]),
                         {tale['_id'], new_tale['_id']})

        resp = self.request(
            path='/tale', method='GET', user=self.user,
            params={'userId': str(self.user['_id'])}
        )
        self.assertStatusOk(resp)
        self.assertEqual(len(resp.json), 2)
        self.assertEqual(set([_['_id'] for _ in resp.json]),
                         {tale['_id'], new_tale['_id']})

        resp = self.request(
            path='/tale', method='GET', user=self.user,
            params={'text': 'new'}
        )
        self.assertStatusOk(resp)
        self.assertEqual(len(resp.json), 1)
        self.assertEqual(set([_['_id'] for _ in resp.json]),
                         {tale['_id']})

        resp = self.request(
            path='/tale/{_id}'.format(**new_tale), method='DELETE',
            user=self.admin)
        self.assertStatusOk(resp)

        resp = self.request(
            path='/tale/{_id}'.format(**new_tale), method='GET',
            user=self.user)
        self.assertStatus(resp, 400)

        resp = self.request(
            path='/tale/{_id}'.format(**tale), method='GET',
            user=self.user)
        self.assertStatusOk(resp)
        for key in tale.keys():
            if key in ('access', 'updated', 'created'):
                continue
            self.assertEqual(resp.json[key], tale[key])

        resp = self.request(
            path='/tale/{_id}/export'.format(**tale),
            method='GET',
            user=self.user,
            type='application/octet-stream',
            isJson=False)

        self.assertStatus(resp, 200)

    def testTaleAccess(self):
        with httmock.HTTMock(mockReposRequest, mockCommitRequest,
                             mockOtherRequest):
            # Grab the default user folders
            resp = self.request(
                path='/folder', method='GET', user=self.user, params={
                    'parentType': 'user',
                    'parentId': self.user['_id'],
                    'sort': 'title',
                    'sortdir': 1
                })
            folder = resp.json[1]
            # Create a new tale from a user image
            resp = self.request(
                path='/tale', method='POST', user=self.user,
                type='application/json',
                body=json.dumps(
                    {
                        'imageId': str(self.image['_id']),
                        'involatileData': [
                            {'type': 'folder', 'id': folder['_id']}
                        ],
                        'public': True
                    })
            )
            self.assertStatusOk(resp)
            tale_user_image = resp.json
            # Create a new tale from an admin image
            resp = self.request(
                path='/tale', method='POST', user=self.user,
                type='application/json',
                body=json.dumps(
                    {
                        'imageId': str(self.image_admin['_id']),
                        'involatileData': [
                            {'type': 'folder', 'id': folder['_id']}
                        ]
                    })
            )
            self.assertStatusOk(resp)
            tale_admin_image = resp.json

        from girder.constants import AccessType

        # Retrieve access control list for the newly created tale
        resp = self.request(
            path='/tale/%s/access' % tale_user_image['_id'], method='GET',
            user=self.user)
        self.assertStatusOk(resp)
        result_tale_access = resp.json
        expected_tale_access = {
            'users': [{
                'login': self.user['login'],
                'level': AccessType.ADMIN,
                'id': str(self.user['_id']),
                'flags': [],
                'name': '%s %s' % (
                    self.user['firstName'], self.user['lastName'])}],
            'groups': []
        }
        self.assertEqual(result_tale_access, expected_tale_access)

        # Update the access control list for the tale by adding the admin
        # as a second user
        input_tale_access = {
            "users": [
                {
                    "login": self.user['login'],
                    "level": AccessType.ADMIN,
                    "id": str(self.user['_id']),
                    "flags": [],
                    "name": "%s %s" % (self.user['firstName'], self.user['lastName'])
                },
                {
                    'login': self.admin['login'],
                    'level': AccessType.ADMIN,
                    'id': str(self.admin['_id']),
                    'flags': [],
                    'name': '%s %s' % (self.admin['firstName'], self.admin['lastName'])
                }],
            "groups": []}
        resp = self.request(
            path='/tale/%s/access' % tale_user_image['_id'], method='PUT',
            user=self.user, params={'access': json.dumps(input_tale_access)})
        self.assertStatusOk(resp)
        # Check that the returned access control list for the tale is as expected
        result_tale_access = resp.json['access']
        result_image_id = resp.json['imageId']
        result_folder_id = resp.json['folderId']
        expected_tale_access = {
            "groups": [],
            "users": [
                {
                    "flags": [],
                    "id": str(self.user['_id']),
                    "level": AccessType.ADMIN
                },
                {
                    "flags": [],
                    "id": str(self.admin['_id']),
                    "level": AccessType.ADMIN
                },
            ]
        }
        self.assertEqual(result_tale_access, expected_tale_access)
        # Check that the access control list propagated to the image that the tale
        # was built from
        resp = self.request(
            path='/image/%s/access' % result_image_id, method='GET',
            user=self.user)
        self.assertStatusOk(resp)
        result_image_access = resp.json
        expected_image_access = input_tale_access
        self.assertEqual(result_image_access, expected_image_access)

        # Check that the access control list propagated to the folder that the tale
        # is associated with
        resp = self.request(
            path='/folder/%s/access' % result_folder_id, method='GET',
            user=self.user)
        self.assertStatusOk(resp)
        result_folder_access = resp.json
        expected_folder_access = input_tale_access
        self.assertEqual(result_folder_access, expected_folder_access)

        # Update the access control list of a tale that was generated from an image that the user
        # does not have admin access to
        input_tale_access = {
            "users": [
                {
                    "login": self.user['login'],
                    "level": AccessType.ADMIN,
                    "id": str(self.user['_id']),
                    "flags": [],
                    "name": "%s %s" % (self.user['firstName'], self.user['lastName'])
                }],
            "groups": []
        }
        resp = self.request(
            path='/tale/%s/access' % tale_admin_image['_id'], method='PUT',
            user=self.user, params={'access': json.dumps(input_tale_access)})
        self.assertStatus(resp, 403)

        # Check that the access control list was correctly set for the tale
        resp = self.request(
            path='/tale/%s/access' % tale_admin_image['_id'], method='GET',
            user=self.user)
        self.assertStatusOk(resp)
        result_tale_access = resp.json
        expected_tale_access = input_tale_access
        self.assertEqual(result_tale_access, expected_tale_access)

        # Check that the access control list did not propagate to the image
        resp = self.request(
            path='/image/%s/access' % tale_admin_image['imageId'], method='GET',
            user=self.user)
        self.assertStatus(resp, 403)

        # Setting the access list with bad json should throw an error
        resp = self.request(
            path='/tale/%s/access' % tale_user_image['_id'], method='PUT',
            user=self.user, params={'access': 'badJSON'})
        self.assertStatus(resp, 400)

        # Change the access to private
        resp = self.request(
            path='/tale/%s/access' % tale_user_image['_id'], method='PUT',
            user=self.user,
            params={'access': json.dumps(input_tale_access), 'public': False})
        self.assertStatusOk(resp)
        resp = self.request(
            path='/tale/%s' % tale_user_image['_id'], method='GET',
            user=self.user)
        self.assertStatusOk(resp)
        self.assertEqual(resp.json['public'], False)

    def tearDown(self):
        self.model('user').remove(self.user)
        self.model('user').remove(self.admin)
        self.model('recipe', 'wholetale').remove(self.recipe)
        self.model('image', 'wholetale').remove(self.image)
        super(TaleTestCase, self).tearDown()
