import requests
from girder.exceptions import RestException


class DataverseVerificator:
    def __init__(self, resource_server, key):
        self.key = key
        self.resource_server = resource_server
        self.token_url = "https://{}/api/users/token".format(resource_server)

    def verify(self):
        headers = {
            "X-Dataverse-key": "{}".format(self.key),
        }
        try:
            r = requests.get(self.token_url, headers=headers)
            r.raise_for_status()
        except requests.exceptions.HTTPError:
            raise RestException(
                "Key '{}' is not valid for '{}'".format(self.key, self.resource_server)
            )
