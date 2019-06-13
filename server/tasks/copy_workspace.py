#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import traceback
from girder.constants import AccessType
from girder.models.folder import Folder
from girder.plugins.jobs.constants import JobStatus
from girder.plugins.jobs.models.job import Job


def run(job):
    jobModel = Job()
    jobModel.updateJob(job, status=JobStatus.RUNNING)

    src_workspace_id, dest_workspace_id = job['args']
    user = job['kwargs']['user']

    try:
        parent = Folder().load(src_workspace_id, user=user, exc=True, level=AccessType.READ)
        workspace = Folder().load(dest_workspace_id, user=user, exc=True)
        Folder().copyFolderComponents(parent, workspace, user, None)
        jobModel.updateJob(job, status=JobStatus.SUCCESS, log="Copying finished")
    except Exception:
        t, val, tb = sys.exc_info()
        log = '%s: %s\n%s' % (t.__name__, repr(val), traceback.extract_tb(tb))
        jobModel.updateJob(job, status=JobStatus.ERROR, log=log)
        raise
