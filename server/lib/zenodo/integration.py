#!/usr/bin/env python
# -*- coding: utf-8 -*-
import cherrypy
import os
from urllib.parse import urlencode, urlparse, urlunparse

from girder.api import access
from girder.api.describe import Description, autoDescribeRoute
from girder.api.rest import boundHandler, RestException
from girder.plugins.oauth.rest import OAuth as OAuthResource

from .. import IMPORT_PROVIDERS


@access.public
@autoDescribeRoute(
    Description("Convert external tools request and bounce it to the dashboard.")
    .param("doi", "The DOI of the dataset.", required=False)
    .param("record_id", "ID", required=False)
    .param("resource_server", "resource server", required=False)
    .param("environment", "The environment that should be selected.", required=False)
)
@boundHandler()
def zenodoDataImport(self, doi, record_id, resource_server, environment):
    """Fetch and unpack a Zenodo record"""
    if not (doi or record_id):
        raise RestException("You need to provide either 'doi' or 'record_id'")

    if not resource_server:
        try:
            resource_server = urlparse(cherrypy.request.headers["Referer"]).netloc
        except KeyError:
            raise RestException("resource_server not set")

    # NOTE: DOI takes precedence over 'record_id' in case both were specified
    if doi:
        # TODO: don't rely on how DOI looks like, I'm not sure if it can't change
        # in the future
        record_id = int(doi.split("zenodo.")[-1])

    user = self.getCurrentUser()
    if user is None:
        redirect = cherrypy.request.base + cherrypy.request.app.script_name
        redirect += cherrypy.request.path_info + "?"
        redirect += urlencode(
            {"record_id": record_id, "resource_server": resource_server}
        )
        redirect += "&token={girderToken}"

        oauth_providers = OAuthResource().listProviders(params={"redirect": redirect})
        raise cherrypy.HTTPRedirect(oauth_providers["Globus"])  # TODO: hardcoded var

    url = "https://{}/record/{}".format(resource_server, record_id)
    provider = IMPORT_PROVIDERS.providerMap["Zenodo"]
    tale = provider.import_tale(url, user)

    # TODO: Make base url a plugin setting, defaulting to dashboard.<domain>
    dashboard_url = os.environ.get("DASHBOARD_URL", "https://dashboard.wholetale.org")
    location = urlunparse(
        urlparse(dashboard_url)._replace(
            path="/run/{}".format(tale["_id"]),
            query="token={}".format(self.getCurrentToken()["_id"]),
        )
    )
    raise cherrypy.HTTPRedirect(location)
