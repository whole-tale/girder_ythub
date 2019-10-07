#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import os
import stat
import sys
import time
import traceback
from webdavfs.webdavfs import WebDAVFS
from fs.base import FS
from fs.copy import copy_fs
from fs.enums import ResourceType
from fs.errors import FileExpected
from fs.error_tools import convert_os_errors
from fs.info import Info
from fs.mode import Mode
from fs.path import basename
from fs.permissions import Permissions
from girderfs.core import WtDmsGirderFS
from girder_client import GirderClient
from girder.constants import AccessType
from girder.models.folder import Folder
from girder.models.token import Token
from girder.utility import config, JsonEncoder
from girder.plugins.jobs.constants import JobStatus
from girder.plugins.jobs.models.job import Job

from ..constants import CATALOG_NAME, InstanceStatus, TaleStatus
from ..lib import pids_to_entities, register_dataMap
from ..lib.dataone import DataONELocations  # TODO: get rid of it
from ..models.instance import Instance
from ..models.tale import Tale
from ..utils import getOrCreateRootFolder


def run(job):
    jobModel = Job()
    jobModel.updateJob(job, status=JobStatus.RUNNING)

    lookup_kwargs, = job["args"]
    user = job["kwargs"]["user"]
    spawn = job["kwargs"]["spawn"]
    tale = job["kwargs"]["tale"]
    token = Token().createToken(user=user, days=0.5)

    progressTotal = 3 + int(spawn)
    progressCurrent = 0

    try:
        # 0. Spawn instance in the background
        if spawn:
            instance = Instance().createInstance(tale, user, token, spawn=spawn)

        # 1. Register data using url
        jobModel.updateJob(
            job,
            status=JobStatus.RUNNING,
            progressTotal=progressTotal,
            progressCurrent=progressCurrent + 1,
            progressMessage="Registering external data",
        )
        dataIds = lookup_kwargs.pop("dataId")
        base_url = lookup_kwargs.get("base_url", DataONELocations.prod_cn)
        dataMap = pids_to_entities(
            dataIds, user=user, base_url=base_url, lookup=True
        )  # DataONE shouldn't be here
        imported_data = register_dataMap(
            dataMap,
            getOrCreateRootFolder(CATALOG_NAME),
            "folder",
            user=user,
            base_url=base_url,
        )

        # Warning: We assume it's coming from a provider that creates a root folder for ds,
        # i.e. it's not HTTP/HTTPS resource, which makes sense at the time when I'm writing this
        # since we support only D1 and DV
        data_folder = Folder().load(imported_data[0], user=user, level=AccessType.READ)
        # Create a dataset with the content of root ds folder, so that it looks nicely and it's easy
        # to copy to workspace later on
        data_set = [
            {"itemId": folder["_id"], "mountPath": "/" + folder["name"]}
            for folder in Folder().childFolders(
                parentType="folder", parent=data_folder, user=user
            )
        ]
        data_set += [
            {"itemId": item["_id"], "mountPath": "/" + item["name"]}
            for item in Folder().childItems(data_folder)
        ]

        # 2. Create a session
        # TODO: yay circular dependencies! IMHO we really should merge wholetale and wt_data_manager
        # plugins...
        from girder.plugins.wt_data_manager.models.session import Session

        # Session is created so that we can easily copy files to workspace, without worrying about
        # how to handler transfers. DMS will do that for us <3
        session = Session().createSession(user, dataSet=data_set)

        # 3. Copy data to the workspace using WebDAVFS
        jobModel.updateJob(
            job,
            status=JobStatus.RUNNING,
            log="Copying files to workspace",
            progressTotal=progressTotal,
            progressCurrent=progressCurrent + 1,
            progressMessage="Copying files to workspace",
        )
        girder_root = "http://localhost:{}".format(
            config.getConfig()["server.socket_port"]
        )
        with WebDAVFS(
            girder_root,
            login=user["login"],
            password="token:{_id}".format(**token),
            root="/tales/{_id}".format(**tale),
        ) as destination_fs, DMSFS(
            str(session["_id"]), girder_root + "/api/v1", str(token["_id"])
        ) as source_fs:
            copy_fs(source_fs, destination_fs)

        Session().deleteSession(user, session)

        # Tale is ready to be built
        tale = Tale().load(tale["_id"], user=user)  # Refresh state
        tale["status"] = TaleStatus.READY
        tale = Tale().updateTale(tale)

        # 4. Wait for container to show up
        if spawn:
            jobModel.updateJob(
                job,
                status=JobStatus.RUNNING,
                log="Waiting for a Tale container",
                progressTotal=progressTotal,
                progressCurrent=progressCurrent + 1,
                progressMessage="Waiting for a Tale container",
            )

            sleep_step = 10
            timeout = 15 * 60
            while instance["status"] == InstanceStatus.LAUNCHING and timeout > 0:
                time.sleep(sleep_step)
                instance = Instance().load(instance["_id"], user=user)
                timeout -= sleep_step
            if timeout <= 0:
                raise RuntimeError(
                    "Failed to launch instance {}".format(instance["_id"])
                )
        else:
            instance = None

    except Exception:
        tale = Tale().load(tale["_id"], user=user)  # Refresh state
        tale["status"] = TaleStatus.ERROR
        tale = Tale().updateTale(tale)
        t, val, tb = sys.exc_info()
        log = "%s: %s\n%s" % (t.__name__, repr(val), traceback.extract_tb(tb))
        jobModel.updateJob(
            job,
            progressTotal=progressTotal,
            progressCurrent=progressTotal,
            progressMessage="Task failed",
            status=JobStatus.ERROR,
            log=log,
        )
        raise

    # To get rid of ObjectId's, dates etc.
    tale = json.loads(
        json.dumps(tale, sort_keys=True, allow_nan=False, cls=JsonEncoder)
    )
    instance = json.loads(
        json.dumps(instance, sort_keys=True, allow_nan=False, cls=JsonEncoder)
    )

    jobModel.updateJob(
        job,
        status=JobStatus.SUCCESS,
        log="Tale created",
        progressTotal=progressTotal,
        progressCurrent=progressTotal,
        progressMessage="Tale created",
        otherFields={"result": {"tale": tale, "instance": instance}},
    )


class DMSFS(FS):
    """Wrapper for WtDmsGirderFS using pyfilesystem.

    This allows to access WtDMS in a pythonic way, without actually mounting it anywhere.
    """

    STAT_TO_RESOURCE_TYPE = {
        stat.S_IFDIR: ResourceType.directory,
        stat.S_IFCHR: ResourceType.character,
        stat.S_IFBLK: ResourceType.block_special_file,
        stat.S_IFREG: ResourceType.file,
        stat.S_IFIFO: ResourceType.fifo,
        stat.S_IFLNK: ResourceType.symlink,
        stat.S_IFSOCK: ResourceType.socket,
    }

    def __init__(self, session_id, api_url, token):
        super().__init__()
        self.session_id = session_id
        gc = GirderClient(apiUrl=api_url)
        gc.token = token
        self._fs = WtDmsGirderFS(session_id, gc)

    def __repr__(self):
        return "{}({})".format(self.__class__.__name__, self.session_id)

    # Required methods
    def getinfo(self, path, namespaces=None):
        self.check()
        namespaces = namespaces or ()
        _path = self.validatepath(path)
        _stat = self._fs.getinfo(_path)

        info = {
            "basic": {"name": basename(_path), "is_dir": stat.S_ISDIR(_stat["st_mode"])}
        }

        if "details" in namespaces:
            info["details"] = {
                "_write": ["accessed", "modified"],
                "accessed": _stat["st_atime"],
                "modified": _stat["st_mtime"],
                "size": _stat["st_size"],
                "type": int(
                    self.STAT_TO_RESOURCE_TYPE.get(
                        stat.S_IFMT(_stat["st_mode"]), ResourceType.unknown
                    )
                ),
            }
        if "stat" in namespaces:
            info["stat"] = _stat

        if "access" in namespaces:
            info["access"] = {
                "permissions": Permissions(mode=_stat["st_mode"]).dump(),
                "uid": 1000,  # TODO: fix
                "gid": 100,  # TODO: fix
            }

        return Info(info)

    def listdir(self, path):
        return self._fs.listdir(path)

    def openbin(self, path, mode="r", buffering=-1, **options):
        _mode = Mode(mode)
        _mode.validate_bin()
        self.check()
        _path = self.validatepath(path)
        if _path == "/":
            raise FileExpected(path)
        with convert_os_errors("openbin", path):
            # TODO: I'm not sure if it's not leaving descriptors open...
            fd = self._fs.open(_path, os.O_RDONLY)
            fdict = self._fs.openFiles[path]
            self._fs._ensure_region_available(path, fdict, fd, 0, fdict["obj"]["size"])
            return open(fdict["path"], "r+b")

    def makedir(self, path, permissions=None, recreate=False):
        pass

    def remove(self, path):
        pass

    def removedir(self, path):
        pass

    def setinfo(self, path, info):
        pass
