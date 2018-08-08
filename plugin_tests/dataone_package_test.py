from tests import base
from girder.api.rest import RestException
from girder.constants import ROOT_DIR
from girder.models.model_base import ValidationException

from d1_client.mnclient_2_0 import MemberNodeClient_2_0
from d1_common.types import dataoneTypes
import uuid
import datetime
import re

def setUpModule():
    base.enabledPlugins.append('wholetale')
    base.startServer()

def tearDownModule():
    base.stopServer()


class TestDataONEUpload(base.TestCase):

    def test_generate_public_access_policy(self):
        from server.dataone_package import generate_public_access_policy
        access_policy = generate_public_access_policy()
        assert(access_policy)

    def test_populate_sys_meta(self):
        # Test that populate_sys_meta has the correct default values
        from server.dataone_package import populate_sys_meta

        pid = str(uuid.uuid4())
        format_id = 'text/csv'
        size=256
        md5='12345'
        name = 'Test Object'
        rights_holder = 'https://orcid.org/0000-0000-0000-0000'

        sys_meta = populate_sys_meta(pid,
                                     format_id,
                                     size,
                                     md5,
                                     name,
                                     rights_holder)
        self.assertEqual(sys_meta.checksum.algorithm, 'MD5')
        self.assertEqual(sys_meta.formatId, format_id)
        self.assertEqual(sys_meta.size, size)
        self.assertEqual(sys_meta.rightsHolder.value(), rights_holder)

    def test_generate_system_metadata(self):
        # Test that the generate_system_metadata is giving the right state

        from server.dataone_package import generate_system_metadata

        pid = str(uuid.uuid4())
        format_id = 'text/csv'
        file_object='12345'
        name = 'Test Object'
        rights_holder = 'https://orcid.org/0000-0000-0000-0000'

        metadata = generate_system_metadata(pid,
                                            format_id,
                                            file_object,
                                            name,
                                            rights_holder)
        self.assertEqual(metadata.size, len(file_object))
        self.assertEqual (metadata.formatId, format_id)
        self.assertEqual (metadata.checksum.algorithm, 'MD5')
        self.assertEqual(metadata.rightsHolder.value(), rights_holder)

    def test_create_resource_map(self):

        from server.dataone_package import create_resource_map

        resmap_pid = str(uuid.uuid4())
        eml_pid = str(uuid.uuid4())
        file_pids = ['1234', '4321']
        res_map = create_resource_map(resmap_pid, eml_pid, file_pids)
        self.assertTrue(bool(len(res_map)))

    def test_create_minimum_eml(self):

        from server.dataone_package import create_minimum_eml
        import xml.etree.cElementTree as ET

        tale = {'title': 'A tale test title', 'description': 'The tale description'}
        user = {'lastName': 'testLastName',
                'firstName': 'testFirstName',
                'email': 'test@test.com'}
        eml_pid ='123456789'
        file_sizes = {'tale_yaml': 123, 'license': 456}

        eml = create_minimum_eml(tale,
                                 user,
                                 [],
                                 eml_pid,
                                 file_sizes,
                                 'CC-BY-3.0',
                                 "http://myorcid")
        root = ET.fromstring(eml)

        expected_root = {'packageId': '123456789',
                         'scope': 'system',
                         'system': 'knb',
                         '{http://www.w3.org/2001/XMLSchema-instance}schemaLocation':
                             'eml://ecoinformatics.org/eml-2.1.1 eml.xsd'}
        self.assertDictEqual(root.attrib, expected_root)

        dataset = root.find('dataset')
        dataset_title = dataset.find('title')
        self.assertEqual(dataset_title.text, tale['title'])

        creator = dataset.find('creator')

        individualName = creator.find('individualName')
        last_name = individualName.find('surName')
        first_name = individualName.find('givenName')
        email = creator.find('electronicMailAddress')

        self.assertEqual(last_name.text, user['lastName'])
        self.assertEqual(first_name.text, user['firstName'])
        self.assertEqual(email.text, user['email'])

        abstract = dataset.find('abstract')
        abstract_para  = abstract.find('para')
        self.assertEqual(abstract_para.text, tale['description'])


    def test_create_minimum_eml_no_abstract(self):

        from server.dataone_package import create_minimum_eml
        import xml.etree.cElementTree as ET

        tale = {'title': 'A tale test title', 'description': ''}
        user = {'lastName': 'testLastName', 'firstName': 'testFirstName'}
        eml_pid ='123456789'

        eml = create_minimum_eml(tale, user, [], eml_pid, {}, 1, "http://myorcid")

        root = ET.fromstring(eml)
        abstract = root.findall('abstract')
        self.assertTrue(not abstract)