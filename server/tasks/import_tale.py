#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import os
import pathlib
import sys
import traceback
from webdavfs.webdavfs import WebDAVFS
from fs.osfs import OSFS
from fs.copy import copy_fs
from girder.models.file import File
from girder.utility import config
from girder.plugins.jobs.constants import JobStatus
from girder.plugins.jobs.models.job import Job

from ..constants import CATALOG_NAME
from ..lib import pids_to_entities, register_dataMap
from ..lib.license import WholeTaleLicense
from ..lib.dataone import DataONELocations  # TODO: get rid of it
from ..models.image import Image
from ..models.tale import Tale
from ..utils import getOrCreateRootFolder


def run(job):
    jobModel = Job()
    jobModel.updateJob(job, status=JobStatus.RUNNING)

    tale_dir, manifest_file = job["args"]
    user = job["kwargs"]["user"]
    token = job["kwargs"]["token"]

    try:
        os.chdir(tale_dir)
        with open(manifest_file, 'r') as manifest_fp:
            manifest = json.load(manifest_fp)

        # Load the environment description
        env_file = os.path.join(os.path.dirname(manifest_file), "environment.json")
        with open(env_file, 'r') as env_fp:
            environment = json.load(env_fp)

        # 1. Register data
        dataIds = [_['identifier'] for _ in manifest["Datasets"]]
        if dataIds:
            jobModel.updateJob(job, status=JobStatus.RUNNING, log="Registering external data")
            dataMap = pids_to_entities(
                dataIds, user=user, base_url=DataONELocations.prod_cn, lookup=True
            )  # DataONE shouldn't be here
            register_dataMap(
                dataMap,
                getOrCreateRootFolder(CATALOG_NAME),
                'folder',
                user=user,
                base_url=DataONELocations.prod_cn,
            )

        # 2. Construct the dataSet
        dataSet = []
        for obj in manifest['aggregates']:
            if 'bundledAs' not in obj:
                continue
            uri = obj['uri']
            fobj = File().findOne({'linkUrl': uri})  # TODO: That's expensive, use something else
            if fobj:
                dataSet.append({
                    'itemId': fobj['itemId'],
                    '_modelType': 'item',
                    'mountPath': obj['bundledAs']['filename']
                })
            # TODO: handle folders

        # 3. Create a Tale
        jobModel.updateJob(job, status=JobStatus.RUNNING, log="Creating a Tale object")
        image = Image().findOne(
            {"name": environment["name"]}
        )  # TODO: create if necessary, for now assume we have it.
        image = Image().filter(image, user)
        icon = image.get(
            "icon",
            (
                "https://raw.githubusercontent.com/"
                "whole-tale/dashboard/master/public/"
                "images/whole_tale_logo.png"
            ),
        )
        licenseSPDX = next(
            (
                _["schema:license"]
                for _ in manifest["aggregates"]
                if "schema:license" in _
            ),
            WholeTaleLicense.default_spdx(),
        )
        authors = " ".join((user["firstName"], user["lastName"]))

        tale = Tale().createTale(
            image,
            dataSet,
            creator=user,
            save=True,
            title=manifest["schema:name"],
            description=manifest["schema:description"],
            public=False,
            config={},
            icon=icon,
            illustration=manifest["schema:image"],
            authors=authors,
            category=manifest["schema:category"],
            licenseSPDX=licenseSPDX,
        )

        # 4. Copy data to the workspace using WebDAVFS (if it exists)
        jobModel.updateJob(
            job, status=JobStatus.RUNNING, log="Copying files to workspace"
        )
        orig_tale_id = pathlib.Path(manifest_file).parts[0]
        for workdir in ("workspace", "data/workspace", None):
            if workdir:
                workdir = os.path.join(orig_tale_id, workdir)
                if os.path.isdir(workdir):
                    break

        if workdir:
            password = "token:{_id}".format(**token)
            root = "/tales/{_id}".format(**tale)
            url = "http://localhost:{}".format(config.getConfig()['server.socket_port'])
            with WebDAVFS(
                url, login=user["login"], password=password, root=root
            ) as webdav_handle:
                copy_fs(OSFS(workdir), webdav_handle)

        jobModel.updateJob(job, status=JobStatus.SUCCESS, log="Tale created")
    except Exception:
        t, val, tb = sys.exc_info()
        log = "%s: %s\n%s" % (t.__name__, repr(val), traceback.extract_tb(tb))
        jobModel.updateJob(job, status=JobStatus.ERROR, log=log)
        raise
