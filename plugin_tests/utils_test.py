import uuid

from tests import base
from girder.api.rest import RestException
from girder.constants import ROOT_DIR
from girder.models.model_base import ValidationException
from girder.models.item import Item
from girder.models.folder import Folder
from girder.models.file import File
from girder.models.user import User
from girder.models.assetstore import Assetstore
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

    def test_getOrCreateRootFolder(self):
        from server.utils import getOrCreateRootFolder
        folder_name = 'folder_name'
        folder_desc = 'folder_description'
        folder = getOrCreateRootFolder(folder_name, folder_desc)

        self.assertEqual(folder['name'], folder_name)
        self.assertEqual(folder['description'], folder_desc)

    def test_create_repository_file(self):
        from server.utils import create_repository_file

        recipe = {'_id': '123456789', 'name': 'test_recipe'}

        # Check that we get `None` back when the assetstore isn't found
        self.assertIsNone(create_repository_file(recipe))

        # Create the assetstore
        Assetstore().createGridFsAssetstore('GridFS local', db='db_name')
        file_id =create_repository_file(recipe)
        print(file_id)
        admin_user = User().getAdmins()[0]
        file = File().load(file_id, user=admin_user)

        self.assertEqual(str(file['_id']), file_id)

    def test_get_dataone_package_url(self):
        from server.utils import get_dataone_package_url
        from server.constants import DataONELocations

        pid = '12345'

        # Test that we get the right url when using dev
        url = get_dataone_package_url(DataONELocations.dev_mn, pid)
        self.assertEqual(url, 'https://dev.nceas.ucsb.edu/#view/'+pid)

        # Test that we get the right url when using prod
        url = get_dataone_package_url(DataONELocations.prod_cn, pid)
        self.assertEqual(url, 'https://search.dataone.org/#view/'+pid)

    def test_extract_orcid_id(self):
        from server.utils import extract_user_id

        # Test with a JWT that has an orcid account
        jwt = "eyJhbGciOiJSUzI1NiJ9.eyJzdWIiOiJodHRwOlwvXC9vcmNpZC5vcm" \
              "dcLzAwMDAtMDAwMi0xNzU2LTIxMjgiLCJmdWxsTmFtZSI6IlRob21hc" \
              "yBUaGVsZW4iLCJpc3N1ZWRBdCI6IjIwMTgtMDgtMDJUMjI6MDY6MDYu" \
              "NDAzKzAwOjAwIiwiY29uc3VtZXJLZXkiOiJ0aGVjb25zdW1lcmtleSI" \
              "sImV4cCI6MTUzMzMxMjM2NiwidXNlcklkIjoiaHR0cDpcL1wvb3JjaW" \
              "Qub3JnXC8wMDAwLTAwMDItMTc1Ni0yMTI4IiwidHRsIjo2NDgwMCwia" \
              "WF0IjoxNTMzMjQ3NTY2fQ.cGnBNtWmLghJj_I0nVpn4S0900eHD0siI" \
              "cYZDW3AHx6B2KDFxnzd9A7l7HDHF3VmtA6te2xkiERQzBUFRqYuKtEE" \
              "WCtX5r4AdkGgEEgozm9a3d8pl1I7YxYG2snhoay0CEZuMlm1KrA9Hoy" \
              "0KVeFRsJw6Eyx8BP3Ftozt7GAEDkPJzNnYdRHc1oyybNgefY8tHNX20" \
              "hEIlsteNkBcQcNuuZRSgUcSCvWajWkrIrDpm1JySPZA5TIjcrSpksTe" \
              "kbCEA7b2KfMRdjfk7ZRaRa0FGVw5K25mDmXbkJ1ScCLUnDMZIW20ENU" \
              "L1PCc6TzAG0_FnWqOcpzsl1bNrRNOFkgyg"

        res = extract_user_id(jwt)
        self.assertEqual(res, "https://orcid.org/0000-0002-1756-2128")

    def test_strip_html_tags(self):
        from server.utils import strip_html_tags

        str_no_html = 'test description'
        str_with_tags = '<p>'+str_no_html+'</p>'
        self.assertEqual(strip_html_tags(str_with_tags), str_no_html)

    def test_is_orcid_id(self):
        from server.utils import is_orcid_id

        # This is what the decoded jwt userid can look like
        input = 'http:\/\/orcid.org\/000-000-000-00'
        res = is_orcid_id(input)
        self.assertTrue(res)

    def test_make_url_https(self):
        from server.utils import make_url_https

        url = 'http://afakeurlthatisntreal'
        res = make_url_https(url)
        self.assertEqual(res, 'https://afakeurlthatisntreal')
