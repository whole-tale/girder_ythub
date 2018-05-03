#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import re
import requests
from urllib.parse import urlparse
from girder.api import access
from girder.api.describe import Description, autoDescribeRoute
from girder.constants import TokenScope, AccessType
from girder.api.docs import addModel
from girder.api.rest import Resource, RestException

from ..dataone_register import D1_lookup
from ..dataone_register import get_package_list
from ..dataone_upload import create_upload_package

dataMap = {
    'type': 'object',
    'description': ('A container with a basic information about '
                    'a set of external data resources.'),
    'properties': {
        'dataId': {
            'type': 'string',
            'description': 'External dataset identificator, such as URL.'
        },
        'repository': {
            'type': 'string',
            'description': 'Name of a data repository holding the dataset.'
        },
        'doi': {
            'type': 'string',
            'description': 'Digital Object Identifier'
        },
        'name': {
            'type': 'string',
            'description': ('A user-friendly name. Defaults to the name '
                            'provided by an external repository.')
        },
        'size': {
            'type': 'integer',
            'description': 'Size of the dataset in bytes.'
        }
    },
    'required': ['dataId', 'repository', 'doi', 'name', 'size'],
    'example': {
        'dataId': 'urn:uuid:42969280-e11c-41a9-92dc-33964bf785c8',
        'doi': '10.5063/F1Z899CZ',
        'name': ('Data from a dynamically downscaled projection of past and '
                 'future microclimates covering North America from 1980-1999 '
                 'and 2080-2099'),
        'repository': 'DataONE',
        'size': 178679
    },
}

fileMap = {
    'type': 'object',
    'description': ('A container with a list of filenames and sizes '
                    'from a DataONE repository.'),
    'properties': {
        'name': {
            'type': 'string',
            'description': 'The name of the data file.'
        },
        'size': {
            'type': 'integer',
            'description': 'Size of the file in bytes.'
        }
    },
    'required': ['name', 'fileList'],
    'example': {
        "Doctoral Dissertation Research: Mapping Community Exposure to Coastal Climate Hazards"
        "in the Arctic: A Case Study in Alaska's North Slope":
            {'fileList':
                [{'science_metadata.xml':
                    {'size': 8961}}],
             'Arctic Slope Shoreline Change Risk Spatial Data Model, 2015-16':
                 {'fileList':
                    [{'science_metadata.xml':
                        {'size': 7577}}]},
             'North Slope Borough shoreline change risk WebGIS usability workshop.':
                 {'fileList':
                    [{'science_metadata.xml':
                        {'size': 7940}}]},
             'Local community verification of shoreline change risks along the Alaskan Arctic Ocean'
                 'coast'
             ' (North Slope).':
                 {'fileList':
                    [{'science_metadata.xml':
                        {'size': 14250}}]},
             'Arctic Slope Shoreline Change Susceptibility Spatial Data Model, 2015-16':
                 {'fileList':
                    [{'science_metadata.xml':
                        {'size': 10491}}]}}
    }
}

addModel('dataMap', dataMap)
addModel('fileMap', fileMap)


def _http_lookup(pid):
    url = urlparse(pid)
    if url.scheme not in ('http', 'https'):
        return
    headers = requests.head(pid).headers

    valid_target = headers.get('Content-Type') is not None
    valid_target = valid_target and ('Content-Length' in headers or
                                     'Content-Range' in headers)
    if not valid_target:
        return

    if 'Content-Disposition' in headers:
        fname = re.search('^.*filename=([\w.]+).*$',
                          headers['Content-Disposition'])
        if fname:
            fname = fname.groups()[0]
    else:
        fname = os.path.basename(url.path.rstrip('/'))

    size = headers.get('Content-Length') or \
        headers.get('Content-Range').split('/')[-1]

    return dict(dataId=pid, doi='unknown', name=fname, repository='HTTP',
                size=int(size))


class Repository(Resource):
    def __init__(self):
        super(Repository, self).__init__()
        self.resourceName = 'repository'

        self.route('GET', ('lookup',), self.lookupData)
        self.route('GET', ('listFiles',), self.listFiles)
        self.route('GET', ('createPackage',), self.createPackage)

    @access.public
    @autoDescribeRoute(
        Description('Create data mapping to an external repository.')
        .notes('Given a list of external data identifiers, '
               'returns mapping to specific repository '
               'along with a basic metadata, such as size, name.')
        .jsonParam('dataId', paramType='query', required=True,
                   description='List of external datasets identificators.')
        .responseClass('dataMap', array=True))
    def lookupData(self, dataId):
        from concurrent.futures import ThreadPoolExecutor, as_completed
        results = []
        futures = {}
        with ThreadPoolExecutor(max_workers=4) as executor:
            for pid in dataId:
                futures[executor.submit(D1_lookup, pid)] = pid
                futures[executor.submit(_http_lookup, pid)] = pid

            for future in as_completed(futures):
                try:
                    if future.result():
                        results.append(future.result())
                except RestException:
                    pass

            return sorted(results, key=lambda k: k['name'])

    @access.public
    @autoDescribeRoute(
        Description('Retrieve a list of files and nested packages in a DataONE repository')
        .notes('Given a list of external data identifiers, '
               'returns a list of files inside along with '
               'their sizes')
        .jsonParam('dataId', paramType='query', required=True,
                   description='List of external datasets identificators.')
        .responseClass('fileMap', array=True))
    def listFiles(self, dataId):
        from concurrent.futures import ThreadPoolExecutor, as_completed
        results = []
        futures = {}
        with ThreadPoolExecutor(max_workers=4) as executor:
            for pid in dataId:
                futures[executor.submit(get_package_list, pid)] = pid
                futures[executor.submit(_http_lookup, pid)] = pid

            for future in as_completed(futures):
                try:
                    if future.result():
                        results.append(future.result())
                except RestException:
                    pass

            return results

    @access.user(scope=TokenScope.DATA_WRITE)
    @autoDescribeRoute(
        Description('Creates a package and uploads it to a data repository')
        .notes('This endpoint should be called when a tale and a series of files need '
               'to be packaged and uploaded to a data repository. \n JSON parameters '
               'should be in the form [{"key": "value"}].'
               'For example, the itemIds parameter should look like [{"itemIds": ["1234, 5678"]}')
        .jsonParam('itemIds',
                   paramType='query',
                   required=True,
                   description='A JSON dict that has a list of item ids that will be included'
                               ' in the package')
        .param('taleId',
               description='The ID of the tale that is will be packaged.',
               required=True)
        .param('repository',
               description='The url for the repositorie\'s endpoint.',
               required=False)
    )
    def createPackage(self, itemIds, taleId, repository):

        user = self.getCurrentUser()
        tale = self.model('tale',
                          'wholetale').load(taleId,
                                            user=user,
                                            level=AccessType.READ)

        create_upload_package(item_ids=itemIds[0]['itemIds'],
                              tale=tale,
                              user=user,
                              repository=repository)
