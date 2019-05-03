from bson import ObjectId
import mock
from tests import base


def setUpModule():
    base.enabledPlugins.append('wholetale')
    base.startServer()

    global JobStatus, Tale
    from girder.plugins.jobs.constants import JobStatus
    from girder.plugins.wholetale.models.tale import Tale


def tearDownModule():
    base.stopServer()


class FakeJob:

    job = {}

    def delay(self, *args, **kwargs):
        return self.job


class PublishTestCase(base.TestCase):
    def setUp(self):
        super(PublishTestCase, self).setUp()
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

        self.tale = self.model('tale', 'wholetale').createTale(
            {'_id': ObjectId()},
            data=[],
            authors=self.user['firstName'] + ' ' + self.user['lastName'],
            creator=self.user,
            public=True,
            description="blah",
            title="Test",
            illustration='linkToImage',
        )

    def testPublish(self):
        with mock.patch('gwvolman.tasks.publish.apply_async'), mock.patch(
            'gwvolman.tasks.publish.delay'
        ) as dl:

            dl.return_value = FakeJob()
            remoteMemberNode = 'remoteMemberURL'
            authToken = 'tokenXXX'

            resp = self.request(
                path='/publish/dataone',
                method='GET',
                user=self.user,
                params={
                    'taleId': str(self.tale['_id']),
                    'remoteMemberNode': remoteMemberNode,
                    'authToken': authToken,
                    'isProduction': False
                },
            )
            self.assertStatusOk(resp)
            job_call = dl.call_args_list[-1][-1]
            job_call.pop('girder_client_token')
            self.assertDictEqual(
                job_call,
                (
                    {
                        'dataone_auth_token': authToken,
                        'dataone_node': remoteMemberNode,
                        'tale': str(self.tale['_id']),
                        'user_id': str(self.user['_id']),
                        'is_production': 'False'
                    }
                ),
            )

    def tearDown(self):
        self.model('user').remove(self.user)
        self.model('user').remove(self.admin)
        super(PublishTestCase, self).tearDown()
