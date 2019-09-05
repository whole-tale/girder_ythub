#!/usr/bin/env python
# -*- coding: utf-8 -*-

from girder.api import access
from girder.api.describe import Description, autoDescribeRoute
from girder.constants import AccessType, TokenScope
from girder.api.rest import Resource, filtermodel
from girder.models.token import Token
from girder.plugins.jobs.models.job import Job

from ..models.tale import Tale

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
    @filtermodel(model=Job)
    @autoDescribeRoute(
        Description('Publish a tale to a repository running Metacat')
        .notes('')
        .modelParam(
            'taleId',
            description='The ID of the tale that is going to be published.',
            model=Tale,
            paramType="query",
            level=AccessType.ADMIN,
            required=True,
        )
        .param(
            'remoteMemberNode',
            description='The endpoint for the Metacat instance, including the endpoint.\n'
            'Example: \'https://dev.nceas.ucsb.edu/knb/d1/mn',
            required=True,
        )
        .param(
            'coordinatingNode',
            description='The coordinating node that will be managing the package.'
            'Example: https://cn.dataone.org/cn/v2 or http://cn-stage-2.test.dataone.org/cn/v2',
            required=True,
        )
        .param(
            'authToken',
            description='The user\'s authentication token for interacting with the '
            'DataONE API. In DataONE\'s case, this is the user\'s JWT'
            'token.',
            required=True,
        )

    )
    def dataonePublish(self, tale, remoteMemberNode, coordinatingNode, authToken):
        user = self.getCurrentUser()
        token = Token().createToken(user=user, days=0.5)

        publishTask = publish.delay(
            tale=str(tale['_id']),
            dataone_node=remoteMemberNode,
            dataone_auth_token=authToken,
            coordinating_node=coordinatingNode,
            user_id=str(user['_id']),
            girder_client_token=str(token['_id'])
        )
        return publishTask.job
