#!/usr/bin/env python
# -*- coding: utf-8 -*-
from girder.api import access
from girder.api.describe import Description, autoDescribeRoute
from girder.api.docs import addModel
from girder.api.rest import Resource

from girder.plugins.wholetale.lib.dataone import DataONELocations
from ..lib import RESOLVERS, IMPORT_PROVIDERS
from ..lib.entity import Entity
from ..lib.data_map import dataMapDoc
from ..lib.file_map import fileMapDoc


addModel('dataMap', dataMapDoc)
addModel('fileMap', fileMapDoc)


class Repository(Resource):
    def __init__(self):
        super(Repository, self).__init__()
        self.resourceName = 'repository'

        self.route('GET', ('lookup',), self.lookupData)
        self.route('GET', ('listFiles',), self.listFiles)

    @staticmethod
    def _buildAndResolveEntity(dataId, base_url, user):
        entity = Entity(dataId, user)
        entity['base_url'] = base_url
        # resolve DOIs, etc.
        return RESOLVERS.resolve(entity)

    @access.public
    @autoDescribeRoute(
        Description('Create data mapping to an external repository.')
        .notes('Given a list of external data identifiers, '
               'returns mapping to specific repository '
               'along with a basic metadata, such as size, name.')
        .jsonParam('dataId', paramType='query', required=True,
                   description='List of external datasets identificators.')
        .param('base_url', 'The node endpoint url. This can be used '
                           'to register datasets from custom networks, '
                           'such as the DataONE development network. This can '
                           'be passed in as an ordinary string. Examples '
                           'include https://dev.nceas.ucsb.edu/knb/d1/mn/v2 and '
                           'https://cn.dataone.org/cn/v2',
               required=False, dataType='string', default=DataONELocations.prod_cn)
        .responseClass('dataMap', array=True))
    def lookupData(self, dataId, base_url):
        # methinks all logic should be in the model or lib and the resource should only
        # delegate to the model/lib.
        # also, why is size required at this point?
        results = []
        for pid in dataId:
            entity = Repository._buildAndResolveEntity(pid, base_url, self.getCurrentUser())
            print(entity)
            provider = IMPORT_PROVIDERS.getProvider(entity)
            results.append(provider.lookup(entity))

        results = [x.toDict() for x in results]
        return sorted(results, key=lambda k: k['name'])

    @access.public
    @autoDescribeRoute(
        Description('Retrieve a list of files and nested packages in a DataONE repository')
        .notes('Given a list of external data identifiers, '
               'returns a list of files inside along with '
               'their sizes')
        .jsonParam('dataId', paramType='query', required=True,
                   description='List of external datasets identificators.')
        .param('base_url', 'The member node base url. This can be used '
                           'to search datasets from custom networks ,'
                           'such as the DataONE development network.',
               required=False, dataType='string',
               default=DataONELocations.prod_cn)
        .responseClass('fileMap', array=True))
    def listFiles(self, dataId, base_url):
        results = []
        for pid in dataId:
            entity = Repository._buildAndResolveEntity(pid, base_url, self.getCurrentUser())
            provider = IMPORT_PROVIDERS.getProvider(entity)
            results.append(provider.listFiles(entity))
        return sorted([x.toDict() for x in results], key=lambda k: list(k))
