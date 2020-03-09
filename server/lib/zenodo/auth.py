import requests
from girder.exceptions import RestException


class ZenodoVerificator:
    def __init__(self, resource_server, key):
        self.key = key
        self.resource_server = resource_server
        self.create_deposition_url = (
            "https://" + resource_server + "/api/deposit/depositions"
        )
        self.delete_deposition_url = self.create_deposition_url + "/{}"

    def verify(self):
        headers = {
            "Authorization": "Bearer {}".format(self.key),
            "Content-Type": "application/json",
        }
        try:
            r = requests.post(self.create_deposition_url, data="{}", headers=headers)
            r.raise_for_status()
            r = requests.delete(
                self.delete_deposition_url.format(r.json()["id"]), headers=headers
            )
            r.raise_for_status()
        except requests.exceptions.HTTPError:
            raise RestException(
                "Key '{}' is not valid for '{}'".format(self.key, self.resource_server)
            )
