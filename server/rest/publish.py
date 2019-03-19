#!/usr/bin/env python
# -*- coding: utf-8 -*-

from girder.api import access
from girder.api.describe import Description, autoDescribeRoute
from girder.constants import TokenScope
from girder.api.rest import Resource
from girder.plugins.jobs.models.job import Job

from gwvolman.tasks import publish


class Publish(Resource):
    """
    Endpoint for publishing Tales to DataOne and Globus.
    """
    def __init__(self):
        super(Publish, self).__init__()
        self.resourceName = 'publish'
        self.route('GET', ('dataone',), self.dataonePublish)

    @access.user(scope=TokenScope.DATA_WRITE)
    @autoDescribeRoute(
        Description('Publish a tale to a repository running Metacat')
        .notes('')
        .param('taleId',
               description='The ID of the tale that is going to be published.',
               required=True)
        .param('remoteMemberNode',
               description='The endpoint for the Metacat instance, including the endpoint.\n'
                           'Example: \'https://dev.nceas.ucsb.edu/knb/d1/mn/v2\'',
               required=True)
        .param('authToken',
               description='The user\'s authentication token for interacting with the '
                           'DataONE API. In DataONE\'s case, this is the user\'s JWT'
                           'token.',
               required=True))
    def dataonePublish(self,
                       taleId,
                       remoteMemberNode,
                       authToken):

        user = self.getCurrentUser()
        token = self.getCurrentToken()

        publishTask = publish.delay(
            tale=taleId,
            dataone_node=remoteMemberNode,
            dataone_auth_token=authToken,
            user_id=str(user['_id']),
            girder_client_token=str(token['_id'])
        )
        return publishTask.job
