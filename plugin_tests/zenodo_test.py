import json
import os
import vcr
from tests import base
from girder.models.folder import Folder
from girder.models.user import User


DATA_PATH = os.path.join(
    os.path.dirname(os.environ["GIRDER_TEST_DATA_PREFIX"]),
    "data_src",
    "plugins",
    "wholetale",
)


def setUpModule():
    base.enabledPlugins.append("wholetale")
    base.startServer()


def tearDownModule():
    base.stopServer()


class ZenodoHarversterTestCase(base.TestCase):
    def setUp(self):
        users = (
            {
                "email": "root@dev.null",
                "login": "admin",
                "firstName": "Root",
                "lastName": "van Klompf",
                "password": "secret",
            },
            {
                "email": "joe@dev.null",
                "login": "joeregular",
                "firstName": "Joe",
                "lastName": "Regular",
                "password": "secret",
            },
        )
        self.admin, self.user = [
            self.model("user").createUser(**user) for user in users
        ]

    @vcr.use_cassette(os.path.join(DATA_PATH, "zenodo_lookup.txt"))
    def testLookup(self):
        resolved_lookup = {
            "dataId": "https://zenodo.org/record/3459420",
            "doi": "doi:10.5281/zenodo.3459420",
            "name": "A global network of biomedical relationships derived from text_ver_7",
            "repository": "Zenodo",
            "size": 8037626747,
        }

        resp = self.request(
            path="/repository/lookup",
            method="GET",
            user=self.user,
            params={
                "dataId": json.dumps(
                    [
                        "https://doi.org/10.5281/zenodo.3459420",
                        "https://zenodo.org/record/3459420",
                    ]
                )
            },
        )
        self.assertStatus(resp, 200)
        self.assertEqual(resp.json, [resolved_lookup, resolved_lookup])

        resolved_listFiles = [
            {
                "jbferet/biodivMapR: v1.0.1_ver_v1.0.1": {
                    "jbferet": {
                        "fileList": [{"biodivMapR-v1.0.1.zip": {"size": 24692383}}]
                    }
                }
            }
        ]

        resp = self.request(
            path="/repository/listFiles",
            method="GET",
            user=self.user,
            params={"dataId": json.dumps(["https://zenodo.org/record/3463499"])},
        )
        self.assertStatus(resp, 200)
        self.assertEqual(resp.json, resolved_listFiles)

    def test_extra_hosts(self):
        from girder.plugins.wholetale.constants import PluginSettings, SettingDefault

        resp = self.request(
            "/system/setting",
            user=self.admin,
            method="PUT",
            params={
                "key": PluginSettings.ZENODO_EXTRA_HOSTS,
                "value": "https://sandbox.zenodo.org/record",
            },
        )
        self.assertStatus(resp, 400)
        self.assertEqual(
            resp.json,
            {
                "field": "value",
                "type": "validation",
                "message": "Zenodo extra hosts setting must be a list.",
            },
        )

        resp = self.request(
            "/system/setting",
            user=self.admin,
            method="PUT",
            params={
                "key": PluginSettings.ZENODO_EXTRA_HOSTS,
                "value": json.dumps(["not a url"]),
            },
        )
        self.assertStatus(resp, 400)
        self.assertEqual(
            resp.json,
            {
                "field": "value",
                "type": "validation",
                "message": "Invalid URL in Zenodo extra hosts",
            },
        )

        # defaults
        resp = self.request(
            "/system/setting",
            user=self.admin,
            method="PUT",
            params={"key": PluginSettings.ZENODO_EXTRA_HOSTS, "value": ""},
        )
        self.assertStatusOk(resp)
        resp = self.request(
            "/system/setting",
            user=self.admin,
            method="GET",
            params={"key": PluginSettings.ZENODO_EXTRA_HOSTS},
        )
        self.assertStatusOk(resp)
        self.assertEqual(
            resp.body[0].decode(),
            str(SettingDefault.defaults[PluginSettings.ZENODO_EXTRA_HOSTS]),
        )

        resp = self.request(
            "/system/setting",
            user=self.admin,
            method="PUT",
            params={
                "list": json.dumps(
                    [
                        {
                            "key": PluginSettings.ZENODO_EXTRA_HOSTS,
                            "value": ["https://sandbox.zenodo.org/record/"],
                        }
                    ]
                )
            },
        )
        self.assertStatusOk(resp)
        from girder.plugins.wholetale.lib.zenodo.provider import ZenodoImportProvider

        self.assertEqual(
            "^http(s)?://(sandbox.zenodo.org/record/|zenodo.org/record/).*$",
            ZenodoImportProvider().regex.pattern,
        )

    @vcr.use_cassette(os.path.join(DATA_PATH, "zenodo_hierarchy.txt"))
    def test_dataset_with_hierarchy(self):
        resp = self.request(
            path="/repository/listFiles",
            method="GET",
            user=self.user,
            params={"dataId": json.dumps(["https://zenodo.org/record/3463499"])},
        )
        self.assertStatus(resp, 200)
        self.assertEqual(
            resp.json[0],
            {
                "jbferet/biodivMapR: v1.0.1_ver_v1.0.1": {
                    "jbferet": {
                        "fileList": [{"biodivMapR-v1.0.1.zip": {"size": 24692383}}]
                    }
                }
            },
        )

    @vcr.use_cassette(os.path.join(DATA_PATH, "zenodo_manifest.txt"))
    def test_manifest_helpers(self):
        resp = self.request(
            path="/repository/lookup",
            method="GET",
            user=self.user,
            params={"dataId": json.dumps(["https://zenodo.org/record/3463499"])},
        )
        self.assertStatus(resp, 200)
        data_map = resp.json

        resp = self.request(
            path="/dataset/register",
            method="POST",
            params={"dataMap": json.dumps(data_map)},
            user=self.user,
        )
        self.assertStatusOk(resp)

        user = User().load(self.user["_id"], force=True)
        dataset_root_folder = Folder().load(user["myData"][0], user=user)
        child_folder = next(
            Folder().childFolders(
                parentType="folder", parent=dataset_root_folder, user=user
            )
        )
        child_item = next((item for item in Folder().childItems(folder=child_folder)))

        from girder.plugins.wholetale.lib.zenodo.provider import ZenodoImportProvider

        for obj in (dataset_root_folder, child_folder, child_item):
            self.assertEqual(
                ZenodoImportProvider().getDatasetUID(obj, user),
                "doi:10.5281/zenodo.3463499",
            )

    def tearDown(self):
        self.model("user").remove(self.user)
        self.model("user").remove(self.admin)
