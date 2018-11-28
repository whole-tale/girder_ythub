#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import cherrypy
import validators
from urllib.parse import urlparse, urlunparse, urlencode
from urllib.error import HTTPError, URLError
from girder.api import access
from girder.api.describe import Description, autoDescribeRoute
from girder.api.rest import Resource, RestException, setResponseHeader

from ..lib.dataverse.provider import DataverseImportProvider


class Integration(Resource):

    def __init__(self):
        super(Integration, self).__init__()
        self.resourceName = 'integration'

        self.route('GET', ('dataverse',), self.dataverseExternalTools)

    @access.public
    @autoDescribeRoute(
        Description('Convert external tools request and bounce it to the dashboard.')
        .param('fileId', 'The Dataverse database ID of a file the external tool has '
               'been launched on.', required=True)
        .param('siteUrl', 'The URL of the Dataverse installation that hosts the file '
               'with the fileId above', required=True)
        .param('apiToken', 'The Dataverse API token of the user launching the external'
               ' tool, if available.', required=False)
        .notes('apiToken is currently ignored.')
    )
    def dataverseExternalTools(self, fileId, siteUrl, apiToken):
        if not validators.url(siteUrl):
            raise RestException('Not a valid URL: siteUrl')
        try:
            fileId = int(fileId)
        except (TypeError, ValueError):
            raise RestException('Invalid fileId (should be integer)')

        site = urlparse(siteUrl)
        url = '{scheme}://{netloc}/api/access/datafile/{fileId}'.format(
            scheme=site.scheme, netloc=site.netloc, fileId=fileId
        )
        query = {'uri': url}
        try:
            title, _, _ = DataverseImportProvider._parse_access_url(urlparse(url))
            query['name'] = title
        except (HTTPError, URLError):
            # This doesn't bode well, but let's fail later when tale import happens
            pass

        # TODO: Make base url a plugin setting, defaulting to dashboard.<domain>
        dashboard_url = os.environ.get('DASHBOARD_URL', 'https://dashboard.wholetale.org')
        location = urlunparse(
            urlparse(dashboard_url)._replace(
                path='/compose',
                query=urlencode(query))
        )
        setResponseHeader('Location', location)
        cherrypy.response.status = 303
