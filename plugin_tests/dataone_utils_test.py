import uuid

from tests import base
from girder.api.rest import RestException
from girder.constants import ROOT_DIR
from girder.models.model_base import ValidationException

from d1_client.mnclient_2_0 import MemberNodeClient_2_0
from d1_common.types import dataoneTypes


def setUpModule():

    base.enabledPlugins.append('wholetale')
    base.startServer()


def tearDownModule():

    base.stopServer()


class TestDataONEUtils(base.TestCase):

    def test_check_pid(self):
        # Test that the pid gets converted to a string if its a number
        from server.dataone_upload import check_pid

        # The most common case will be a uuid
        pid = uuid.uuid4()
        pid = check_pid(pid)

        self.assertTrue(isinstance(pid, str))

        # Check that it works if numbers are accidentally used
        pid = 1234
        pid = check_pid(pid)
        self.assertTrue(isinstance(pid, str))