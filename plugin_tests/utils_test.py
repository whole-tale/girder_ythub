import uuid

from tests import base
from girder.api.rest import RestException
from girder.constants import ROOT_DIR
from girder.models.model_base import ValidationException
from girder.models.item import Item
from girder.models.folder import Folder
from girder.models.file import File
from girder.models.user import User
from d1_client.mnclient_2_0 import MemberNodeClient_2_0
from d1_common.types import dataoneTypes


def setUpModule():

    base.enabledPlugins.append('wholetale')
    base.startServer()


def tearDownModule():

    base.stopServer()


class TestDataONEUtils(base.TestCase):

    def setUp(self):
        super(TestDataONEUtils, self).setUp()
        user_details = {
            'email': 'root2@dev.null',
            'login': 'admin2',
            'firstName': 'Root2',
            'lastName': 'van Klompf2',
            'password': 'secret'
        }
        assetstore = {'_id': 0}

        self.user = User().createUser(**user_details)

        c1 = self.model('collection').createCollection('c1', self.user)
        self.f1 = self.model('folder').createFolder(
            c1, 'f1', parentType='collection')

        # Holds the file on the assetstore
        self.item_1 = Item().createItem('i1', self.user, self.f1)

        # Holds the file that points to a DataONE object
        self.item_2 = Item().createItem('i2', self.user, self.f1)

        # Holds the file that doesn't point to a DataONE object
        self.item_3 = Item().createItem('i3', self.user, self.f1)

        # A file that exists in the assetstore
        self.file_1 = File().createFile(self.user, self.item_1, 'foo1', 7, assetstore)

        # A link file that points to an object on DataONE
        self.url = 'https://cn.dataone.org/cn/v2/resolve/'
        self.link_file = File().createLinkFile(name='testLinkFile',
                                                 parent=self.item_2,
                                                 parentType='item',
                                                 url=self.url,
                                                 creator=self.user)

        # A link file that doesn't point to dataOne
        self.link_file_2 = File().createLinkFile(name='testLinkFile',
                                                 parent=self.item_3,
                                                 parentType='item',
                                                 url='http://dev.null',
                                                 creator=self.user)


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

    def test_get_file_item(self):
        # Test that files are being properly extracted out of items
        from server.utils import get_file_item

        # Test the case where the item doesn't exist
        file = get_file_item('5a9d9ab2bb33576598e85b1b' ,self.user)
        self.assertEqual(file, None)

        # Test the case where there is a file in the item
        file = get_file_item(self.item_1['_id'], self.user)
        self.assertTrue(bool(file))

        # Test the case where the item is empty
        empty_item = self.model('item').createItem('item_1', self.user, self.f1)
        file = get_file_item(empty_item['_id'], self.user)
        self.assertEqual(file, None)

    def test_get_remote_url(self):
        # Test that the url is getting extracted from linkFiles
        from server.utils import get_remote_url
        url = get_remote_url(self.item_2['_id'], self.user)
        self.assertEqual(url, self.url)

        # Test that we get None back if there isn't a url
        url = get_remote_url(self.item_1['_id'], self.user)
        self.assertEqual(url, None)

    def test_get_dataone_url(self):
        # Test that only dataone urls are returned
        from server.utils import get_dataone_url
        url = get_dataone_url(self.item_2['_id'], self.user)
        self.assertEqual(url, self.url)

        # Check that if the url isn't DataONE, we get None back
        result = get_dataone_url(self.item_3['_id'], self.user)
        self.assertEqual(result, None)

    def test_delete_keys_from_dict(self):
        from server.utils import delete_keys_from_dict

        my_dict = {'key1': [{'nested1': '1', 'nested2': 2}],
                  'key2': {'nested3': 4}}
        del_keys = ['nested2', 'nested3']
        new_dict = delete_keys_from_dict(my_dict, del_keys)
        print(new_dict)
        self.assertRaises(KeyError, new_dict['key2']['nested3'])
        self.assertRaises(KeyError, new_dict['key1']['nested1'])
