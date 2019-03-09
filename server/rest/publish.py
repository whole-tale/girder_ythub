#!/usr/bin/env python
# -*- coding: utf-8 -*-

from girder.api import access
from girder.api.describe import Description, autoDescribeRoute
from girder.constants import TokenScope
from girder.api.rest import Resource
from girder.plugins.jobs.models.job import Job


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
        .jsonParam(name='itemIds',
                   required=True,
                   description='A list of item ids of files that are going to be included in '
                               'the package.\n'
                               'Example: ["item1", "item2", "item3"]')
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
               required=True)
                   required=False)
    )
    def dataonePublish(self,
                       itemIds,
                       taleId,
                       remoteMemberNode,
                       authToken):

        user = self.getCurrentUser()
        token = self.getCurrentToken()

        jobTitle = 'Publishing Tale to DataONE'
        jobModel = Job()

        args = (itemIds,
                taleId,
                remoteMemberNode,
                authToken,
                str(token['_id']),
                str(user['_id']))
        job = jobModel.createJob(
            title=jobTitle, type='publish', handler='worker_handler',
            user=user, public=False, args=args, kwargs={},
            otherFields={
                'celeryTaskName': 'gwvolman.tasks.publish'
            })
        jobModel.scheduleJob(job)
        return job
