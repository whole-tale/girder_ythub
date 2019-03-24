import mock
import json
from tests import base


def setUpModule():
    base.enabledPlugins.append('wholetale')
    base.startServer()

    global JobStatus, Tale
    from girder.plugins.jobs.constants import JobStatus
    from girder.plugins.wholetale.models.tale import Tale


def tearDownModule():
    base.stopServer()


class PublishTestCase(base.TestCase):

    def setUp(self):
        super(PublishTestCase, self).setUp()
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

    @mock.patch('gwvolman.tasks.publish')
    def testPublish(self, it):
        with mock.patch('girder_worker.task.celery.Task.apply_async', spec=True) \
                as mock_apply_async:

            taleId = 'abc123'
            remoteMemberNode = 'remoteMemberURL'
            authToken = 'tokenXXX'

            mock_apply_async().job.return_value = json.dumps({'job': 1, 'blah': 2})
            resp = self.request(
                path='/publish/dataone', method='GET', user=self.user,
                     params={
                         'taleId': taleId,
                         'remoteMemberNode': remoteMemberNode,
                         'authToken': authToken
                     })
            self.assertStatusOk(resp)
            job_call = mock_apply_async.call_args_list[-1][-1]
            self.assertEqual(job_call['headers']['girder_job_title'], 'Publish Tale')
            self.assertEqual(
                job_call['kwargs'],
                ({
                    'dataone_auth_token': authToken,
                    'dataone_node': remoteMemberNode,
                    'tale': taleId,
                    'user_id': str(self.user['_id'])
                })
            )

    def tearDown(self):
        self.model('user').remove(self.user)
        self.model('user').remove(self.admin)
        super(PublishTestCase, self).tearDown()
