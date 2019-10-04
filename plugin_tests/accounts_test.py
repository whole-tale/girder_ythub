import json
import httmock
from tests import base
from girder.models.setting import Setting
from girder.models.user import User
from girder.models.token import Token
from girder.exceptions import ValidationException

AUTH_PROVIDERS = [
    {
        "id": "orcid",
        "logo": "",
        "name": "ORCID",
        "tags": ["publish"],
        "url": "",
        "type": "bearer",
        "state": "unauthorized",
    },
    {
        "id": "zenodo",
        "logo": "",
        "name": "Zenodo",
        "tags": ["data", "publish"],
        "url": "",
        "type": "apikey",
        "docs_href": "https://zenodo.org/account/settings/applications/tokens/new/",
        "targets": [],
    },
]

DATAONE_PROVIDER = {
    "id": "dataoneprod",
    "logo": "",
    "name": "DataONE Production CN",
    "tags": ["publish"],
    "url": "",
    "type": "dataone",
    "state": "unauthorized",
}

APIKEY_GROUPS = [{"id": "zenodo", "targets": ["sandbox.zenodo.org", "zenodo.org"]}]


@httmock.urlmatch(
    scheme="https", netloc="orcid.org", path="/oauth/token", method="POST"
)
def mockGetOrcidToken(url, request):
    return json.dumps({"access_token": "blah"})


@httmock.urlmatch(
    scheme="https", netloc="orcid.org", path="/oauth/revoke", method="POST"
)
def mockRevokeOrcidToken(url, request):
    return json.dumps({})


@httmock.all_requests
def mockOtherRequests(url, request):
    raise Exception("Unexpected url %s" % str(request.url))


def setUpModule():
    base.enabledPlugins.append("wholetale")
    base.startServer()


def tearDownModule():
    base.stopServer()


class ExternalAccountsTestCase(base.TestCase):
    def setUp(self):
        super(ExternalAccountsTestCase, self).setUp()
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
        from girder.plugins.oauth.constants import PluginSettings as OAuthPluginSettings

        Setting().set(OAuthPluginSettings.ORCID_CLIENT_ID, "orcid_client_id")
        Setting().set(OAuthPluginSettings.ORCID_CLIENT_SECRET, "orcid_client_secret")
        Setting().set(OAuthPluginSettings.PROVIDERS_ENABLED, ["orcid"])

    def test_default_settings(self):
        from girder.plugins.wholetale.constants import SettingDefault, PluginSettings

        for key, error_msg in (
            (
                PluginSettings.EXTERNAL_AUTH_PROVIDERS,
                "^Invalid External Auth Providers.*$",
            ),
            (
                PluginSettings.EXTERNAL_APIKEY_GROUPS,
                "^Invalid External Apikey Groups.*$",
            ),
        ):

            self.assertEqual(Setting().get(key), SettingDefault.defaults[key])

            with self.assertRaisesRegex(ValidationException, error_msg):
                Setting().set(key, "blah")

    def test_list_accounts(self):
        from girder.plugins.wholetale.constants import SettingDefault, PluginSettings

        Setting().set(PluginSettings.EXTERNAL_AUTH_PROVIDERS, AUTH_PROVIDERS)
        Setting().set(PluginSettings.EXTERNAL_APIKEY_GROUPS, APIKEY_GROUPS)

        resp = self.request(
            path="/account",
            method="GET",
            user=self.user,
            params={"redirect": "http://localhost"},
        )
        self.assertStatusOk(resp)
        accounts = resp.json

        self.assertEqual(
            sorted([_["id"] for _ in accounts]),
            sorted([_["id"] for _ in AUTH_PROVIDERS]),
        )
        orcid_account = next((_ for _ in accounts if _["id"] == "orcid"))
        self.assertTrue(
            "%2Fapi%2Fv1%2Faccount%2Forcid%2Fcallback" in orcid_account["url"]
        )

        resp = self.request(
            path="/account/zenodo/targets", method="GET", user=self.user
        )
        self.assertStatusOk(resp)
        zenodo_targets = resp.json
        self.assertEqual(zenodo_targets, APIKEY_GROUPS[0]["targets"])

        # Pretend we have authorized with Orcid and one Zenodo target
        other_tokens = [
            {
                "provider": "orcid",
                "access_token": "orcid_token",
                "resource_server": "orcid.org",
                "token_type": "bearer",
            },
            {
                "provider": "zenodo",
                "access_token": "zenodo_key",
                "resource_server": "sandbox.zenodo.org",
                "token_type": "apikey",
            },
            {
                "provider": "that_is_not_supported",
                "access_token": "blah",
                "resource_server": "example.org",
                "token_type": "dataone",
            },
            {
                "provider": "zenodo",
                "access_token": "blah",
                "resource_server": "example.org",
                "token_type": "apikey",
            },
        ]
        self.user["otherTokens"] = other_tokens
        self.user = User().save(self.user)

        resp = self.request(path="/account/foo/targets", method="GET", user=self.user)
        self.assertStatus(resp, 400)
        self.assertEqual(resp.json["message"], 'Unknown provider "foo".')

        resp = self.request(
            path="/account/zenodo/targets", method="GET", user=self.user
        )
        self.assertStatusOk(resp)
        zenodo_targets = resp.json
        self.assertEqual(zenodo_targets, ["zenodo.org"])

        resp = self.request(
            path="/account",
            method="GET",
            user=self.user,
            params={"redirect": "http://localhost"},
        )
        self.assertStatusOk(resp)
        accounts = resp.json

        orcid_account = next((_ for _ in accounts if _["id"] == "orcid"))
        self.assertEqual(orcid_account["state"], "authorized")
        self.assertTrue(orcid_account["url"].endswith("/account/orcid/revoke"))

        zenodo_account = next((_ for _ in accounts if _["id"] == "zenodo"))
        self.assertEqual(
            zenodo_account["targets"][0]["resource_server"], "sandbox.zenodo.org"
        )

        # Return to defaults
        for key in (
            PluginSettings.EXTERNAL_AUTH_PROVIDERS,
            PluginSettings.EXTERNAL_APIKEY_GROUPS,
        ):
            Setting().set(key, SettingDefault.defaults[key])
        self.user["otherTokens"] = []
        self.user = User().save(self.user)

    def test_callback(self):
        provider_info = AUTH_PROVIDERS[0]  # ORCID

        # Try callback, for a nonexistent provider
        resp = self.request(path="/account/foobar/callback")
        self.assertStatus(resp, 400)

        # Try callback, without providing any params
        resp = self.request(path="/account/%s/callback" % provider_info["id"])
        self.assertStatus(resp, 400)

        # Try callback, providing params as though the provider failed
        resp = self.request(
            method="GET",
            path="/account/%s/callback" % provider_info["id"],
            params={"code": None, "error": "some_custom_error"},
            exception=True,
        )
        self.assertStatus(resp, 502)
        self.assertEqual(
            resp.json["message"], "Provider returned error: 'some_custom_error'."
        )

        resp = self.request(
            method="GET",
            path="/account/%s/callback" % provider_info["id"],
            params={"code": "orcid_code", "state": "some_state"},
        )
        self.assertStatus(resp, 403)
        self.assertEqual(
            resp.json["message"], 'Invalid CSRF token (state="some_state").'
        )

        invalid_token_no_user = Token().createToken(user=None, days=0.25)
        state = "{_id}.blah".format(**invalid_token_no_user)
        resp = self.request(
            method="GET",
            path="/account/%s/callback" % provider_info["id"],
            params={"code": "orcid_code", "state": state},
        )
        self.assertStatus(resp, 400)
        self.assertTrue(resp.json["message"].startswith("No valid user"))

        invalid_token_expired = Token().createToken(user=self.user, days=1e-10)
        state = "{_id}.blah".format(**invalid_token_expired)
        resp = self.request(
            method="GET",
            path="/account/%s/callback" % provider_info["id"],
            params={"code": "orcid_code", "state": state},
        )
        self.assertStatus(resp, 403)
        self.assertTrue(resp.json["message"].startswith("Expired CSRF token"))

        valid_token = Token().createToken(user=self.user, days=0.25)
        invalid_state = "{_id}".format(**valid_token)
        resp = self.request(
            method="GET",
            path="/account/%s/callback" % provider_info["id"],
            params={"code": "orcid_code", "state": invalid_state},
        )
        self.assertStatus(resp, 400)
        self.assertTrue(resp.json["message"].startswith("No redirect"))

        valid_token = Token().createToken(user=self.user, days=0.25)
        valid_state = "{_id}.blah".format(**valid_token)
        with httmock.HTTMock(mockGetOrcidToken, mockOtherRequests):
            resp = self.request(
                method="GET",
                path="/account/%s/callback" % provider_info["id"],
                params={"code": "orcid_code", "state": valid_state},
                isJson=False,
            )
        self.assertStatus(resp, 303)
        self.assertTrue("girderToken" in resp.cookie)

        self.user = User().load(self.user["_id"], force=True)
        self.assertEqual(self.user["otherTokens"][0]["provider"], "orcid")
        self.assertEqual(self.user["otherTokens"][0]["access_token"], "blah")
        self.assertEqual(self.user["otherTokens"][0]["resource_server"], "orcid")

        # Change token to see if it updates
        self.user["otherTokens"][0]["access_token"] = "different_blah"
        self.user = User().save(self.user)
        valid_token = Token().createToken(user=self.user, days=0.25)
        valid_state = "{_id}.blah".format(**valid_token)
        with httmock.HTTMock(mockGetOrcidToken, mockOtherRequests):
            resp = self.request(
                method="GET",
                path="/account/%s/callback" % provider_info["id"],
                params={"code": "orcid_code", "state": valid_state},
                isJson=False,
            )
        self.assertStatus(resp, 303)
        self.user = User().load(self.user["_id"], force=True)
        self.assertEqual(self.user["otherTokens"][0]["access_token"], "blah")

        # Reset to defaults
        self.user["otherTokens"] = []
        self.user = User().save(self.user)

    def test_revoke(self):
        from girder.plugins.wholetale.constants import SettingDefault, PluginSettings

        Setting().set(PluginSettings.EXTERNAL_AUTH_PROVIDERS, AUTH_PROVIDERS)
        Setting().set(PluginSettings.EXTERNAL_APIKEY_GROUPS, APIKEY_GROUPS)

        self.user["otherTokens"] = [
            {
                "provider": "orcid",
                "access_token": "orcid_token",
                "resource_server": "orcid.org",
                "token_type": "bearer",
                "refresh_token": "orcid_refresh_token",
            },
            {
                "provider": "zenodo",
                "access_token": "zenodo_key",
                "resource_server": "sandbox.zenodo.org",
                "token_type": "apikey",
            },
        ]
        self.user = User().save(self.user)
        valid_token = Token().createToken(user=self.user, days=0.25)

        resp = self.request(
            method="GET",
            path="/account/foo/revoke",
            params={"redirect": "somewhere", "token": valid_token["_id"]},
        )
        self.assertStatus(resp, 400)
        self.assertEqual(
            resp.json["message"], "Invalid account provider (provider=foo)"
        )

        with httmock.HTTMock(mockRevokeOrcidToken, mockOtherRequests):
            resp = self.request(
                method="GET",
                path="/account/orcid/revoke",
                params={"redirect": "https://somewhere", "token": valid_token["_id"]},
                isJson=False,
            )
            self.assertStatus(resp, 303)
            self.assertEqual(resp.headers["location"], "https://somewhere")

        self.user = User().load(self.user["_id"], force=True)
        self.assertEqual(len(self.user["otherTokens"]), 1)
        self.assertEqual(self.user["otherTokens"][0]["provider"], "zenodo")

        resp = self.request(
            method="GET",
            path="/account/zenodo/revoke",
            params={"redirect": "somewhere", "token": valid_token["_id"]},
        )
        self.assertStatus(resp, 400)
        self.assertTrue(resp.json["message"].startswith("Missing resource_server"))

        current_other_tokens = self.user["otherTokens"]
        resp = self.request(
            method="GET",
            path="/account/zenodo/revoke",
            params={
                "redirect": "somewhere",
                "resource_server": "zenodo.org",  # non exisiting, should be noop
                "token": valid_token["_id"],
            },
            isJson=False,
        )
        self.assertStatus(resp, 303)
        self.user = User().load(self.user["_id"], force=True)
        self.assertEqual(current_other_tokens, self.user["otherTokens"])

        resp = self.request(
            method="GET",
            path="/account/zenodo/revoke",
            params={
                "redirect": "somewhere",
                "resource_server": "sandbox.zenodo.org",
                "token": valid_token["_id"],
            },
            isJson=False,
        )
        self.assertStatus(resp, 303)
        self.user = User().load(self.user["_id"], force=True)
        self.assertEqual(self.user["otherTokens"], [])

        # Return to defaults
        for key in (
            PluginSettings.EXTERNAL_AUTH_PROVIDERS,
            PluginSettings.EXTERNAL_APIKEY_GROUPS,
        ):
            Setting().set(key, SettingDefault.defaults[key])

    def test_adding_apikeys(self):
        from girder.plugins.wholetale.constants import SettingDefault, PluginSettings

        Setting().set(PluginSettings.EXTERNAL_AUTH_PROVIDERS, [AUTH_PROVIDERS[1]])
        Setting().set(PluginSettings.EXTERNAL_APIKEY_GROUPS, APIKEY_GROUPS)

        resp = self.request(
            method="POST",
            path="/account/foo/key",
            params={"resource_server": "blah", "key": "key"},
            user=self.user,
        )
        self.assertStatus(resp, 400)
        self.assertEqual(resp.json["message"], 'Unknown provider "foo".')

        resp = self.request(
            method="POST",
            path="/account/zenodo/key",
            params={"resource_server": "blah", "key": "key"},
            user=self.user,
        )
        self.assertStatus(resp, 400)
        self.assertEqual(resp.json["message"], 'Unsupported resource server "blah".')

        resp = self.request(
            method="POST",
            path="/account/zenodo/key",
            params={"resource_server": "sandbox.zenodo.org", "key": "key"},
            user=self.user,
        )
        self.assertStatusOk(resp)

        self.user = User().load(self.user["_id"], force=True)
        self.assertEqual(
            self.user["otherTokens"][0]["resource_server"], "sandbox.zenodo.org"
        )
        self.assertEqual(self.user["otherTokens"][0]["access_token"], "key")

        # Update
        resp = self.request(
            method="POST",
            path="/account/zenodo/key",
            params={"resource_server": "sandbox.zenodo.org", "key": "newkey"},
            user=self.user,
        )
        self.assertStatusOk(resp)

        self.user = User().load(self.user["_id"], force=True)
        self.assertEqual(len(self.user["otherTokens"]), 1)
        self.assertEqual(
            self.user["otherTokens"][0]["resource_server"], "sandbox.zenodo.org"
        )
        self.assertEqual(self.user["otherTokens"][0]["access_token"], "newkey")

        # Return to defaults
        for key in (
            PluginSettings.EXTERNAL_AUTH_PROVIDERS,
            PluginSettings.EXTERNAL_APIKEY_GROUPS,
        ):
            Setting().set(key, SettingDefault.defaults[key])
        self.user["otherTokens"] = []
        User().save(self.user)

    def test_dataone(self):
        from girder.plugins.wholetale.constants import SettingDefault, PluginSettings

        Setting().set(PluginSettings.EXTERNAL_AUTH_PROVIDERS, [DATAONE_PROVIDER])

        resp = self.request(
            path="/account",
            method="GET",
            user=self.user,
            params={"redirect": "http://localhost"},
        )
        self.assertStatusOk(resp)
        accounts = resp.json
        self.assertEqual(
            accounts[0]["url"], "https://cn.dataone.org/portal/oauth?action=start"
        )

        resp = self.request(
            method="POST",
            path="/account/dataoneprod/key",
            params={
                "resource_server": "sandbox.zenodo.org",
                "key": "dataone_token",
                "key_type": "dataone",
            },
            user=self.user,
        )
        self.assertStatusOk(resp)

        self.user = User().load(self.user["_id"], force=True)
        self.assertEqual(len(self.user["otherTokens"]), 1)
        self.assertEqual(
            self.user["otherTokens"][0]["resource_server"], "cn.dataone.org"
        )
        self.assertEqual(self.user["otherTokens"][0]["access_token"], "dataone_token")

        # Return to defaults
        for key in (PluginSettings.EXTERNAL_AUTH_PROVIDERS,):
            Setting().set(key, SettingDefault.defaults[key])
        self.user["otherTokens"] = []
        User().save(self.user)
