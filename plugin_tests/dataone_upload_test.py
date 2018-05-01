from tests import base
from girder.api.rest import RestException
from girder.constants import ROOT_DIR
from girder.models.model_base import ValidationException

from d1_client.mnclient_2_0 import *
from d1_common.types import dataoneTypes
import uuid


def setUpModule():

    base.enabledPlugins.append('wholetale')
    base.startServer()


def tearDownModule():

    base.stopServer()


class TestDataONEUpload(base.TestCase):

    def test_create_client(self):
        # Test that a client to a DataONE member node is being created
        from server.dataone_upload import create_client

        member_node='https://dev.nceas.ucsb.edu/knb/d1/mn/'
        header = {"headers": {
            "Authorization": "Bearer TOKEN"}}
        print(type(header))
        client = create_client(member_node, header)
        self.assertIsNotNone(client)

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

    def test_upload_failure(self):
        # Test that we're throwing exceptions when uploading fails
        from server.dataone_upload import upload_file
        from server.dataone_upload import create_client
        from server.dataone_upload import generate_system_metadata

        member_node = 'https://dev.nceas.ucsb.edu/knb/d1/mn/'
        header = {"headers": {
            "Authorization": "Bearer TOKEN"}}
        client = create_client(member_node, header)
        pid = str(uuid.uuid4())
        object = 'test data'

        sys_meta = generate_system_metadata(pid, 'text/csv', object)

        self.assertRaises(ValidationException, upload_file, client, pid, object, sys_meta)
