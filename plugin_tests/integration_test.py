#!/usr/bin/env python
# -*- coding: utf-8 -*-
import mock
import os
import vcr
from tests import base
from urllib.parse import urlparse, parse_qs

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


class IntegrationTestCase(base.TestCase):
    def setUp(self):
        super(IntegrationTestCase, self).setUp()
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

        self.admin, self.user = [User().createUser(**user) for user in users]

    @vcr.use_cassette(os.path.join(DATA_PATH, "dataverse_integration.txt"))
    def testDataverseIntegration(self):
        error_handling_cases = [
            (
                {"fileId": "1234", "siteUrl": "definitely not a URL"},
                "Not a valid URL: siteUrl",
            ),
            ({"siteUrl": "https://dataverse.someplace"}, "No data Id provided"),
            (
                {"fileId": "not_a_number", "siteUrl": "https://dataverse.someplace"},
                "Invalid fileId (should be integer)",
            ),
            (
                {"datasetId": "not_a_number", "siteUrl": "https://dataverse.someplace"},
                "Invalid datasetId (should be integer)",
            ),
        ]

        for params, errmsg in error_handling_cases:
            resp = self.request(
                "/integration/dataverse", method="GET", params=params, user=self.user
            )
            self.assertStatus(resp, 400)
            self.assertEqual(resp.json, {"message": errmsg, "type": "rest"})

        def dv_dataset(flag):
            uri = "https://dataverse.harvard.edu"
            if flag == "dataset_pid":
                uri += "/dataset.xhtml?persistentId=doi:10.7910/DVN/TJCLKP"
            elif flag == "datafile":
                uri += "/api/access/datafile/3371438"
            elif flag == "datafile_pid":
                uri += "/file.xhtml?persistentId=doi:10.7910/DVN/TJCLKP/3VSTKY"
            elif flag == "dataset_id":
                uri += "/api/datasets/3035124"

            return {
                "uri": [uri],
                "name": ["Open Source at Harvard"],
                "asTale": ["True"],
            }

        valid_cases = [
            (
                {"fileId": "3371438", "siteUrl": "https://dataverse.harvard.edu"},
                dv_dataset("dataset_pid"),
            ),
            (
                {
                    "fileId": "3371438",
                    "siteUrl": "https://dataverse.harvard.edu",
                    "fullDataset": False,
                },
                dv_dataset("datafile"),
            ),
            (
                {
                    "filePid": "doi:10.7910/DVN/TJCLKP/3VSTKY",
                    "siteUrl": "https://dataverse.harvard.edu",
                    "fullDataset": False,
                },
                dv_dataset("datafile_pid"),
            ),
            (
                {
                    "filePid": "doi:10.7910/DVN/TJCLKP/3VSTKY",
                    "siteUrl": "https://dataverse.harvard.edu",
                    "fullDataset": True,
                },
                dv_dataset("dataset_pid"),
            ),
            (
                {
                    "datasetPid": "doi:10.7910/DVN/TJCLKP",
                    "siteUrl": "https://dataverse.harvard.edu",
                    "fullDataset": False,
                },
                dv_dataset("dataset_pid"),
            ),
            (
                {
                    "datasetId": "3035124",
                    "siteUrl": "https://dataverse.harvard.edu",
                    "fullDataset": False,
                },
                dv_dataset("dataset_pid"),
            ),
        ]

        for params, response in valid_cases:
            resp = self.request(
                "/integration/dataverse", method="GET", params=params, user=self.user
            )
            self.assertStatus(resp, 303)
            self.assertEqual(
                parse_qs(urlparse(resp.headers["Location"]).query), response
            )

    def testDataoneIntegration(self):
        from girder.plugins.wholetale.lib.data_map import DataMap

        class fakeProvider:
            def lookup(self, entity):
                return DataMap("urn:uuid:12345.6789", 0)

        with mock.patch(
            "girder.plugins.wholetale.lib.dataone.integration.DataOneImportProvider",
            fakeProvider,
        ):
            resp = self.request(
                "/integration/dataone",
                method="GET",
                user=self.user,
                params={
                    "uri": "urn:uuid:12345.6789",
                    "title": "dataset title",
                    "environment": "rstudio",
                },
            )

        self.assertStatus(resp, 303)
        query = parse_qs(urlparse(resp.headers["Location"]).query)
        self.assertEqual(query["name"][0], "dataset title")
        self.assertEqual(query["uri"][0], "urn:uuid:12345.6789")
        self.assertEqual(query["environment"][0], "rstudio")

    def tearDown(self):
        User().remove(self.user)
        User().remove(self.admin)
        super(IntegrationTestCase, self).tearDown()
