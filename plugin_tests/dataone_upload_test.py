from tests import base
from girder.api.rest import RestException
from girder.constants import ROOT_DIR
from girder.models.model_base import ValidationException

from d1_client.mnclient_2_0 import MemberNodeClient_2_0
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
