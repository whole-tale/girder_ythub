#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import traceback
import zipfile
from pathlib import Path
import json

from ..models.tale import Tale
from ..models.instance import Instance

from girder import logger
from girder.constants import AccessType, TokenScope
from girder.models.folder import Folder
from girder.models.file import File
from girder.models.item import Item
from girder.models.token import Token
from girder.plugins.jobs.constants import JobStatus
from girder.plugins.jobs.models.job import Job
from girder.plugins.jobs.constants import REST_CREATE_JOB_TOKEN_SCOPE

from gwvolman.tasks import register_dataset


def create_tale_payload(manifest_data, user, imageId=None):
    """
    Creates the structure that's needed to send to POST /tale. It contains
    the essential information to create a Tale
    :param manifest_data: Data from a Tale's manifest file
    :param imageId: Optional ID of the image that the Tale will use
    :return: A struct holding the properties of the Tale
    :rtype: dict
    """
    payload = {
        'authors': manifest_data.get('createdBy').get('schema:givenName') + ' ' + manifest_data.get('createdBy').get(
            'schema:familyName'),
        'title': manifest_data.get('schema:name'),
        'public': False,
        'published': False,
        'description': manifest_data.get('schema:description'),
        'category': manifest_data.get('schema:category'),
        'icon': manifest_data.get('schema:image'),
        'illustration': 'https://raw.githubusercontent.com/'
                        'whole-tale/dashboard/master/public/'
                        'images/demo-graph2.jpg',
        'save': True,

    }
    if imageId:
        payload['imageId']=imageId
    return payload


def run(job):
    """
    Takes a zipped Tale and turns it into a Tale
    :return:
    """

    jobModel = Job()
    jobModel.updateJob(job, status=JobStatus.RUNNING)

    zip_item_id = job['kwargs']['itemId']
    user = job['kwargs']['user']
    token = job['kwargs']['token']
    Token().addScope(token, scope=REST_CREATE_JOB_TOKEN_SCOPE)

    zip_item = Item().load(id=zip_item_id, user=user)
    zip_file = Item().childFiles(item=zip_item, user=user)[0]
    zip_path = File().getLocalFilePath(zip_file)

    try:
        tale_zip = zipfile.ZipFile(zip_path)
    except FileNotFoundError:
        errormsg = 'Could not find zipped Tale'
        raise ValueError(errormsg)

    # The files in the zip need to be referenced from the root, which should be the
    # name of the Tale
    tale_zip.namelist()[0]
    path = Path(tale_zip.namelist()[0])
    zip_root = str(path.parts[0])

    # Try opening the files that are needed to re-create the Tale object
    try:
        manifest_data = tale_zip.read(zip_root+'/'+'metadata/manifest.json')
        manifest_data = json.loads(manifest_data.decode("utf-8").replace("'", '"'))
    except KeyError:
        errormsg = 'Failed to open a manifest file'
        raise ValueError(errormsg)
    try:
        environment_data = tale_zip.read(zip_root + '/' + 'environment.txt').decode("utf-8")
    except KeyError:
        errormsg = 'Failed to read the environment information'
        raise ValueError(errormsg)

    payload = create_tale_payload(manifest_data, user, environment_data)
    logger.info(payload)
    """
    Register each dataset that's in the "Datasets" array in the manifest 
    """

    for dataset_record in manifest_data.get('Datasets'):
        tale_task = register_dataset.apply_async(dataset_record['@id'])
        logger.info('Foubnd dataset record')
        logger.info(str(dataset_record))
        resource = tale_task.wait(timeout=None, interval=0.5)
        logger.info('Finished registering')
        logger.info(str(resource))
        payload['dataSet'].append(
            {'mountPath': '/' + resource['name'], 'itemId': resource['_id']}
        ),

    tale = Tale().createTale(payload)
    instance = Instance().createInstance(tale, user, token, name=payload['title'],
                                            save=True, spawn=True)

    while instance['status'] == InstanceStatus.LAUNCHING:
        # TODO: Timeout? Raise error?
        time.sleep(1)
        instance = Instance().load(instance['_id'])
    else:
        instance = None

    self.job_manager.updateProgress(
        message='Tale is ready!')
    jobModel.updateJob(job, status=JobStatus.SUCCESS, log="Tale import finished")

    return 'done'
    #return {'tale': tale, 'instance': instance}