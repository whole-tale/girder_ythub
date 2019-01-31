#!/usr/bin/env python
# -*- coding: utf-8 -*-
from girder.api import access
from girder.api.describe import Description, autoDescribeRoute
from girder.api.rest import Resource, RestException
from girder.constants import AccessType, SortDir
from girder.models.folder import Folder
from girder.models.user import User
from ..constants import WORKSPACE_NAME
from ..models.tale import Tale
from ..utils import getOrCreateRootFolder


class Workspace(Resource):
    def __init__(self):
        super(Workspace, self).__init__()
        self.resourceName = 'workspace'

        self.route('GET', (), self.listWorkspaces)
        self.route('GET', (':id',), self.getWorkspace)

    @access.public
    @autoDescribeRoute(
        Description(('Returns all workspaces that user has access to'))
        .param('userId', "The ID of the parent Tale's creator.", required=False)
        .pagingParams(defaultSort='name', defaultSortDir=SortDir.ASCENDING)
        .responseClass('folder', array=True)
    )
    def listWorkspaces(self, userId, limit, offset, sort):
        workspaces = []
        parent = getOrCreateRootFolder(WORKSPACE_NAME)

        if userId:
            user = User().load(userId, force=True, exc=True)
        else:
            user = None

        if sort[0][0] in {'name', 'lowerName'}:
            sort = [('title', sort[0][1])]

        for tale in Tale().list(
            user=user,
            limit=limit,
            offset=offset,
            sort=sort,
            currentUser=self.getCurrentUser(),
        ):
            q = {'parentId': parent['_id'], 'name': str(tale['_id'])}
            folder = Folder().findOne(q)
            if folder:
                folder['_modelType'] = 'folder'
                folder['name'] = tale['title']
                folder['lowerName'] = folder['name'].lower()
                workspaces.append(folder)

        return workspaces

    @access.public
    @autoDescribeRoute(
        Description('Get the workspace associated with a Tale ID')
        .modelParam(
            'id',
            description='The ID of a Tale',
            model='tale',
            plugin='wholetale',
            level=AccessType.READ,
        )
        .responseClass('folder')
        .errorResponse('Tale ID was invalid.')
        .errorResponse('Read access was denied for the resource.', 403)
    )
    def getWorkspace(self, tale):
        user = self.getCurrentUser()

        parent = getOrCreateRootFolder(WORKSPACE_NAME)
        filters = {'name': str(tale['_id'])}
        try:
            folder = next(
                Folder().childFolders(
                    parentType='folder', parent=parent, user=user, filters=filters
                )
            )
        except StopIteration:
            raise RestException(
                "Tale ({}) doesn't have a workspace".format(tale['_id'])
            )

        folder['_modelType'] = 'folder'
        folder['name'] = tale['title']
        folder['lowerName'] = folder['name'].lower()
        return folder
