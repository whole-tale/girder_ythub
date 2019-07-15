#!/usr/bin/env python
# -*- coding: utf-8 -*-
from girder.api.docs import addModel

publishInfoSchema = {
    'title': 'publishInfo',
    'description': 'A schema representing publishing information',
    'type': 'object',
    'properties': {
        "pid": {
            "type": ["string", "null"],
            "description": "A unique identifier assigned to this tale from a "
                           "publishing source."
        },
        "uri": {
            "type": ["string", "null"],
            "description": "A URI pointing to the location of the published "
                           "Tale."
        },
        "date": {
            'type': 'string',
            'format': 'date-time',
            "description": "Date Tale was published."
        }
    },
    'required': ['pid', 'uri', 'date']
}

publishInfoListSchema = {
    'title': 'list of publishInfos',
    'type': 'array',
    'items': publishInfoSchema,
}

dataResourceSchema = {
    'title': 'dataResource',
    'description': 'A schema representing data elements used in WholeTale',
    'type': 'object',
    'properties': {
        'type': {
            'type': 'string',
            'enum': ['item', 'folder'],
            'description': 'Either a Girder item or a Girder folder'
        },
        'id': {
            'type': 'string',
            'description': 'Girder object id'
        }
    },
    'required': ['type', 'id']
}


dataMapSchema = {
    'title': 'dataMap',
    'description': 'A schema for a WholeTale Data Map',
    'type': 'object',
    'properties': {
        'dataId': {
            'type': 'string',
            'description': ('An internal unique identifier specific '
                            'to a given repository.'),
        },
        'doi': {
            'type': ['string', 'null'],
            'description': 'A unique Digital Object Identifier'
        },
        'name': {
            'type': 'string'
        },
        'repository': {
            'type': 'string',
            'description': 'A name of the repository holding the data.'
        },
        'size': {
            'type': 'integer',
            'minimum': -1,
            'description': 'The total size of the dataset in bytes.'
        }
    },
    'required': ['dataId', 'repository']
}

dataMapListSchema = {
    'title': 'list of dataMaps',
    'type': 'array',
    'items': dataMapSchema,
}

dataSetItemSchema = {
    'title': 'dataSetItem',
    'description': 'A schema representing data elements used in DMS dataSets',
    'type': 'object',
    'properties': {
        '_modelType': {
            'type': 'string',
            'enum': ['item', 'folder'],
            'description': 'Either a Girder item or a Girder folder'
        },
        'itemId': {
            'type': 'string',
            'description': 'ID of a Girder item or a Girder folder'
        },
        'mountPath': {
            'type': 'string',
            'description': 'An absolute path where the item/folder are mounted in the EFS'
        }
    },
    'required': ['itemId', 'mountPath']
}

dataSetSchema = {
    'title': 'A list of resources with a corresponding mount points in the ESF',
    'type': 'array',
    'items': dataSetItemSchema,
}

tagsSchema = {
    'title': 'tags',
    'description': 'A schema for image tags',
    'type': 'array',
    'items': {
        'type': 'string'
    }
}

containerConfigSchema = {
    'title': 'containerConfig',
    'description': 'A subset of docker runtime configuration used for Tales',
    'type': 'object',
    'properties': {
        'command': {
            'type': 'string',
            'description': 'Command to run when the container starts'
        },
        'cpuShares': {
            'type': 'string',
        },
        'environment': {
            'type': 'array',
            'description': 'List of environment variables passed to a container',
            'items': {
                'type': 'string',
                'description': 'Environment variable, in the form KEY=val'
            }
        },
        'memLimit': {
            'type': 'string',
        },
        'port': {
            'type': 'integer',
            'description': ('The exposed internal port that is going to be '
                            'accessbile through HTTP(S)')
        },
        'user': {
            'type': 'string',
            'description': 'Username used inside the running container'
        },
        'targetMount': {
            'type': 'string',
            'description': ('Path where the Whole Tale filesystem '
                            'will be mounted')
        },
        'urlPath': {
            'type': 'string',
            'description': ('Subpath appended to the randomly generated '
                            'container URL')
        }
    }
}

containerInfoSchema = {
    'title': 'containerInfo',
    'description': 'A subset of docker info parameters used by Tales',
    'type': 'object',
    'properties': {
        'created': {
            'type': 'string',
            'format': 'date-time',
        },
        'name': {
            'type': 'string',
        },
        'imageId': {
            'type': 'string',
            'description': ("ID of the successfully built image "
                            "that was used to run this instance."),
        },
        'digest': {
            'type': 'string',
            'description': ("Checksum of the successfully built image "
                            "that was used to run this instance."),
        },
        'nodeId': {
            'type': 'string',
        },
        'mountPoint': {
            'type': 'string',
        },
        'volumeName': {
            'type': 'string',
        },
        'urlPath': {
            'type': 'string',
        }
    },
    'required': ['name', 'mountPoint', 'nodeId', 'volumeName'],
}

imageInfoSchema = {
    'title': 'imageInfo',
    'description': 'Attributes describing a Tale image',
    'type': 'object',
    'properties': {
        'created': {
            'type': 'string',
            'format': 'date-time',
        },
        'jobId': {
            'type': 'string',
        },
        'digest': {
            'type': 'string',
        },
        'fullName': {
            'type': 'string',
        }
    }
}

"""
  {
    "_id": "5d0d369c5276b9e30d9cbc73",
    "_modelType": "item",
    "baseParentId": "5cdde4ca84f03ea7329bab0d",
    "baseParentType": "user",
    "created": "2019-06-21T19:57:16.031000+00:00",
    "creatorId": "5cdde4ca84f03ea7329bab0d",
    "description": "",
    "folderId": "5cdde4ca84f03ea7329bab0e",
    "name": "biocaddie.json",
    "size": 570,
    "updated": "2019-06-21T19:57:16.031000+00:00"
  }
"""
itemSchema = {
    'title': 'Upload',
    'description': 'Attributes describing an item in Girder',
    'type': 'object',
    'properties': {
        '_id': {
            'type': 'string',
        },
        '_modelType': {
            'type': 'string',
        },
        'baseParentId': {
            'type': 'string',
        },
        'baseParentType': {
            'type': 'string',
        },
        'created': {
            'type': 'string',
            'format': 'date-time'
        },
        'creatorId': {
            'type': 'string',
        },
        'description': {
            'type': 'string',
        },
        'name': {
            'type': 'string',
        },
        'folderId': {
            'type': 'string',
        },
        'size': {
            'type': 'integer',
        },
        'updated': {
            'type': 'string',
            'format': 'date-time'
        }
    }
}


"""
  {
    "_accessLevel": 2,
    "_id": "5cdde4ca84f03ea7329bab0f",
    "_modelType": "folder",
    "baseParentId": "5cdde4ca84f03ea7329bab0d",
    "baseParentType": "user",
    "created": "2019-05-16T22:31:38.653000+00:00",
    "creatorId": "5cdde4ca84f03ea7329bab0d",
    "description": "",
    "name": "Data",
    "parentCollection": "user",
    "parentId": "5cdde4ca84f03ea7329bab0d",
    "public": false,
    "size": 0,
    "updated": "2019-05-16T22:31:38.653000+00:00"
  }
"""
folderSchema = {
   'title': 'Folder',
    'description': 'Attributes describing a folder in Girder',
    'type': 'object',
    'properties': {
        '_accessLevel': {
            'type': 'string',
        },
        '_id': {
            'type': 'string',
        },
        '_modelType': {
            'type': 'string',
        },
        'baseParentId': {
            'type': 'string',
        },
        'baseParentType': {
            'type': 'string',
        },
        'created': {
            'type': 'string',
            'format': 'date-time'
        },
        'creatorId': {
            'type': 'string',
        },
        'description': {
            'type': 'string',
        },
        'name': {
            'type': 'string',
        },
        'parentCollection': {
            'type': 'string',
        },
        'parentId': {
            'type': 'string',
        },
        'public': {
            'type': 'boolean',
        },
        'size': {
            'type': 'integer',
        },
        'updated': {
            'type': 'string',
            'format': 'date-time'
        }
    }
}

stringSchema = {
    'title': 'string',
    'description': 'A string',
    'type': 'object',
    'properties': {
        'value': {
            'type': 'string',
            'description': 'Value of the string'
        }
    }
}

addModel('containerConfig', containerConfigSchema)
addModel('containerInfo', containerInfoSchema)
addModel('imageInfo', imageInfoSchema)
addModel('publishInfo', publishInfoSchema)
addModel('dataSet', dataSetSchema)

addModel('Folder', folderSchema)
addModel('Upload', itemSchema)
addModel('Item', itemSchema)
addModel('File', itemSchema)
addModel('Collection', folderSchema)
addModel('Assetstore', folderSchema)
addModel('Group', itemSchema)

addModel('Setting', itemSchema)
addModel('job', itemSchema)
addModel('Token', itemSchema)
addModel('User', itemSchema)
addModel('folder', folderSchema)

addModel('string', stringSchema)

# TODO: Item, Group, Collection, Assetstore
