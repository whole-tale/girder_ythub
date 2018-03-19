import mock
import httmock
import six
from tests import base
from girder.exceptions import ValidationException
from .tests_helpers import \
    GOOD_REPO, GOOD_COMMIT, \
    mockOtherRequest, mockCommitRequest, mockReposRequest


def setUpModule():
    base.enabledPlugins.append('wholetale')
    base.startServer()


def tearDownModule():
    base.stopServer()


class FakeAsyncResult(object):
    def __init__(self):
        self.task_id = 'fake_id'

    def get(self, timeout=None):
        return dict(
            nodeId='123456',
            mountPoint='/foo/bar',
            volumeName='blah_volume',
            name='tmp-blah',
            urlPath='?token=foo'
        )


class TaleTestCase(base.TestCase):

    def setUp(self):
        super(TaleTestCase, self).setUp()
        global PluginSettings, instanceCapErrMsg
        from girder.plugins.wholetale.constants import PluginSettings
        from girder.plugins.wholetale.rest.instance import instanceCapErrMsg
        self.model('setting').set(
            PluginSettings.TMPNB_URL, 'https://tmpnb.null')
        self.model('setting').set(
            PluginSettings.INSTANCE_CAP, '2')
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
        self.image = self.model('image', 'wholetale').createImage(
            self.recipe, GOOD_REPO, name="my name", creator=self.user,
            public=True)

        self.userPrivateFolder = self.model('folder').createFolder(
            self.user, 'PrivateFolder', parentType='user', public=False,
            creator=self.user)
        self.userPublicFolder = self.model('folder').createFolder(
            self.user, 'PublicFolder', parentType='user', public=True,
            creator=self.user)

        data = [{'type': 'folder', 'id': self.userPrivateFolder['_id']}]
        self.tale_one = self.model('tale', 'wholetale').createTale(
            self.image, data, creator=self.user,
            title='tale one', public=True, config={'memLimit': '2g'})
        data = [{'type': 'folder', 'id': self.userPublicFolder['_id']}]
        self.tale_two = self.model('tale', 'wholetale').createTale(
            self.image, data, creator=self.user,
            title='tale two', public=True, config={'memLimit': '1g'})

    def testInstanceFromImage(self):
        return  # FIXME
        with mock.patch('celery.Celery') as celeryMock:
            with mock.patch('tornado.httpclient.HTTPClient') as tornadoMock:
                instance = celeryMock.return_value
                instance.send_task.return_value = FakeAsyncResult()

                req = tornadoMock.return_value
                req.fetch.return_value = {}

                resp = self.request(
                    path='/instance', method='POST', user=self.user,
                    params={})
                self.assertStatus(resp, 400)
                self.assertEqual(resp.json['message'],
                                 'You need to provide "imageId" or "taleId".')
                resp = self.request(
                    path='/instance', method='POST', user=self.user,
                    params={'imageId': str(self.image['_id'])})

                self.assertStatusOk(resp)
                self.assertEqual(
                    resp.json['url'], 'https://tmp-blah.0.0.1/?token=foo')
                self.assertEqual(
                    resp.json['name'], 'Testing %s' % self.image['fullName'])
                instanceId = resp.json['_id']

                resp = self.request(
                    path='/instance', method='POST', user=self.user,
                    params={'imageId': str(self.image['_id'])})
                self.assertStatusOk(resp)
                self.assertEqual(resp.json['_id'], instanceId)

            resp = self.request(
                path='/instance/{}'.format(instanceId), method='DELETE',
                user=self.user)
            self.assertStatusOk(resp)

    def testInstanceCap(self):
        with six.assertRaisesRegex(self, ValidationException,
                                   '^Instance Cap needs to be set.$'):
            self.model('setting').set(PluginSettings.INSTANCE_CAP, '')
        with six.assertRaisesRegex(self, ValidationException,
                                   '^Instance Cap needs to be an integer.$'):
            self.model('setting').set(PluginSettings.INSTANCE_CAP, 'a')

        setting = self.model('setting')

        with mock.patch('celery.Celery') as celeryMock:
            with mock.patch('tornado.httpclient.HTTPClient') as tornadoMock:
                instance = celeryMock.return_value
                instance.send_task.return_value = FakeAsyncResult()

                req = tornadoMock.return_value
                req.fetch.return_value = {}

                current_cap = setting.get(PluginSettings.INSTANCE_CAP)
                setting.set(PluginSettings.INSTANCE_CAP, '0')
                resp = self.request(
                    path='/instance', method='POST', user=self.user,
                    params={'imageId': str(self.image['_id'])})
                self.assertStatus(resp, 400)
                self.assertEqual(
                    resp.json['message'], instanceCapErrMsg.format('0'))
                setting.set(PluginSettings.INSTANCE_CAP, current_cap)

    def testInstanceFlow(self):
        return  # FIXME

        with mock.patch('celery.Celery') as celeryMock:
            with mock.patch('tornado.httpclient.HTTPClient') as tornadoMock:
                instance = celeryMock.return_value
                instance.send_task.return_value = FakeAsyncResult()

                req = tornadoMock.return_value
                req.fetch.return_value = {}

                resp = self.request(
                    path='/instance', method='POST', user=self.user,
                    params={'taleId': str(self.tale_one['_id']),
                            'name': 'tale one'}
                )
        self.assertStatusOk(resp)
        self.assertEqual(resp.json['url'], 'https://tmp-blah.0.0.1/?token=foo')
        self.assertEqual(resp.json['name'], 'tale one')
        self.assertEqual(resp.json['containerInfo']['volumeName'], 'blah_volume')
        instance_one = resp.json

        with mock.patch('celery.Celery') as celeryMock:
            instance = celeryMock.return_value
            instance.send_task.return_value = FakeAsyncResult()
            resp = self.request(
                path='/instance', method='POST', user=self.user,
                params={'taleId': str(self.tale_two['_id'])},
            )
            self.assertStatusOk(resp)
            instance_two = resp.json

            resp = self.request(
                path='/instance', method='POST', user=self.admin,
                params={'taleId': str(self.tale_one['_id'])},
            )
            self.assertStatusOk(resp)
            instance_three = resp.json

            # Make sure that instance is a singleton
            resp = self.request(
                path='/instance', method='POST', user=self.admin,
                params={'taleId': str(self.tale_one['_id'])},
            )
            self.assertStatusOk(resp)
            self.assertEqual(resp.json['_id'], instance_three['_id'])

        resp = self.request(
            path='/instance', method='GET', user=self.user,
            params={}
        )
        self.assertStatusOk(resp)
        self.assertEqual(set([_['_id'] for _ in resp.json]),
                         {instance_one['_id'], instance_two['_id']})

        resp = self.request(
            path='/instance', method='GET', user=self.admin,
            params={'taleId': str(self.tale_one['_id'])}
        )
        self.assertStatusOk(resp)
        self.assertEqual(set([_['_id'] for _ in resp.json]),
                         {instance_one['_id'], instance_three['_id']})

        resp = self.request(
            path='/instance', method='GET', user=self.admin,
            params={'taleId': str(self.tale_one['_id']),
                    'userId': str(self.admin['_id'])}
        )
        self.assertStatusOk(resp)
        self.assertEqual(set([_['_id'] for _ in resp.json]),
                         {instance_three['_id']})

        with mock.patch('celery.Celery') as celeryMock:
            instance = celeryMock.return_value
            instance.send_task.return_value = FakeAsyncResult()
            resp = self.request(
                path='/instance/{_id}'.format(**instance_two), method='DELETE',
                user=self.user)
            self.assertStatusOk(resp)

        resp = self.request(
            path='/instance/{_id}'.format(**instance_two), method='GET',
            user=self.user)
        self.assertStatus(resp, 400)

        resp = self.request(
            path='/instance/{_id}'.format(**instance_one), method='GET',
            user=self.user)
        self.assertStatusOk(resp)
        for key in instance_one.keys():
            if key in ('access', 'updated', 'created', 'lastActivity'):
                continue
            self.assertEqual(resp.json[key], instance_one[key])

    def tearDown(self):
        self.model('folder').remove(self.userPrivateFolder)
        self.model('folder').remove(self.userPublicFolder)
        self.model('recipe', 'wholetale').remove(self.recipe)
        self.model('image', 'wholetale').remove(self.image)
        self.model('tale', 'wholetale').remove(self.tale_one)
        self.model('tale', 'wholetale').remove(self.tale_two)
        self.model('user').remove(self.user)
        self.model('user').remove(self.admin)
        super(TaleTestCase, self).tearDown()
