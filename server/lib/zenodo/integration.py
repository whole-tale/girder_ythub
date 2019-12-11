#!/usr/bin/env python
# -*- coding: utf-8 -*-
import cherrypy
import json
import os
from urllib.parse import urlencode, urlparse, urlunparse
from urllib.request import Request, urlopen

from girder.api import access
from girder.api.describe import Description, autoDescribeRoute
from girder.api.rest import boundHandler

from ...models.tale import Tale


@access.public
@autoDescribeRoute(
    Description("Convert external tools request and bounce it to the dashboard.")
    .param("doi", "The DOI of the dataset.", required=False)
    .param("record_id", "ID", required=False)
    .param("resource_server", "resource server", required=False)
    .param("environment", "The environment that should be selected.", required=False)
    .notes("apiToken is currently ignored.")
)
@boundHandler()
def zenodoDataImport(self, doi, record_id, resource_server, environment):
    """Fetch and unpack a Zenodo record"""
    if not (doi or record_id):
        raise RestException("You need to provide either 'doi' or 'record_id'")

    if not resource_server:
        resource_server = urlparse(cherrypy.request.headers["Referer"]).netloc

    # NOTE: DOI takes precedence over 'record_id' in case both were specified
    if doi:
        # TODO: don't rely on how DOI looks like, I'm not sure if it can't change
        # in the future
        record_id = int(doi.split("zenodo.")[-1])

    user = self.getCurrentUser()
    if user is None:
        redirect = (
            cherrypy.request.base
            + cherrypy.request.app.script_name
            + cherrypy.request.path_info
            + "?"
            + urlencode({"record_id": record_id, "resource_server": resource_server})
            + "&token={girderToken}"
        )
        oauth_providers = cherrypy.request.app.root.v1.oauth.listProviders(
            params={"redirect": redirect}
        )
        raise cherrypy.HTTPRedirect(oauth_providers["Globus"])  # TODO: hardcoded var

    req = Request(
        "https://{}/api/records/{}".format(resource_server, record_id),
        headers={
            "accept": "application/vnd.zenodo.v1+json",
            "User-Agent": "Whole Tale",
        },
    )
    resp = urlopen(req)
    record = json.loads(resp.read().decode("utf-8"))

    has_tale_keyword = "Tale" in record["metadata"]["keywords"]
    files = record["files"]
    only_one_file = len(files) == 1

    if not (has_tale_keyword and only_one_file):
        raise RestException(
            "{} doesn't look like a Tale.".format(record["links"]["record_html"])
        )

    file_ref = files[0]
    if file_ref["type"] != "zip":
        raise RuntimeError("Not a zipfile")

    file_url = file_ref["links"]["self"]
    # fname = os.path.basename(deep_get(file_ref, "key"))

    def stream_zipfile(chunk_size):
        with urlopen(file_url) as src:
            while True:
                data = src.read(chunk_size)
                if not data:
                    break
                yield data

    temp_dir, manifest_file, manifest, environment = Tale()._extractZipPayload(
        stream_zipfile
    )

    publishInfo = [
        {
            "pid": record["doi"],
            "uri": record["links"]["doi"],
            "date": record["created"],
            "repository_id": str(record["id"]),
            "repository": resource_server,
        }
    ]
    tale = Tale().createTaleFromStream(
        stream_zipfile, user=user, publishInfo=publishInfo
    )
    # TODO: Make base url a plugin setting, defaulting to dashboard.<domain>
    dashboard_url = os.environ.get("DASHBOARD_URL", "https://dashboard.wholetale.org")
    location = urlunparse(
        urlparse(dashboard_url)._replace(
            path="/run/{}".format(tale["_id"]),
            query="token={}".format(self.getCurrentToken()["_id"]),
        )
    )
    raise cherrypy.HTTPRedirect(location)
