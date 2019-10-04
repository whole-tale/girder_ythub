from urllib.parse import urlparse, urlunparse
from d1_common.env import D1_ENV_DICT

from girder.plugins.oauth.providers.base import ProviderBase

# Because, why would they keep up to date list of CNs and deployments?
D1_ENV_DICT["stage2"] = dict(base_url="https://cn-stage-2.test.dataone.org/cn")


class FakeDataONE(ProviderBase):
    @classmethod
    def get_cn(cls):
        key = cls.__name__.lower().replace("dataone", "")
        return D1_ENV_DICT[key]["base_url"]

    @classmethod
    def getUrl(cls, state):
        auth_url = urlparse(cls.get_cn())._replace(
            path="/portal/oauth", query="action=start"
        )
        return urlunparse(auth_url)
