#!/usr/bin/env python
# -*- coding: utf-8 -*-

import git
import json
import os
import re
import shutil
import time
from girder.models.folder import Folder
from girder.models.token import Token
from girder.models.user import User
from girder.utility import JsonEncoder
from girder.plugins.jobs.constants import JobStatus
from girder.plugins.jobs.models.job import Job

from ..constants import InstanceStatus, TaleStatus
from ..models.instance import Instance
from ..models.tale import Tale


def run(job):
    jobModel = Job()
    jobModel.updateJob(job, status=JobStatus.RUNNING)

    url, = job["args"]
    if "@" in url:
        repo_url, branch = url.split("@")
    else:
        repo_url = url
        branch = None

    user = User().load(job["userId"], force=True)
    tale = Tale().load(job["kwargs"]["taleId"], user=user)
    spawn = job["kwargs"]["spawn"]
    change_status = job["kwargs"].get("change_status", True)
    token = Token().createToken(user=user, days=0.5)

    progressTotal = 1 + int(spawn)
    progressCurrent = 0

    try:
        workspace = Folder().load(tale["workspaceId"], force=True)
        has_dot_git_already = os.path.isdir(os.path.join(workspace["fsPath"], ".git"))
        if has_dot_git_already:
            raise RuntimeError(
                "Workspace is already a git repository. You need to remove it "
                "before trying to add a new one."
            )

        # 1. Checkout the git repo
        jobModel.updateJob(
            job,
            status=JobStatus.RUNNING,
            progressTotal=progressTotal,
            progressCurrent=progressCurrent,
            progressMessage="Cloning the git repo",
        )

        try:
            repo = git.Repo.init(workspace["fsPath"])
            origin = repo.create_remote("origin", repo_url)
            origin.fetch()
            if not branch:
                gcmd = git.cmd.Git(workspace["fsPath"])
                remote_info = gcmd.execute(["git", "remote", "show", "origin"])
                branch = re.search("HEAD branch: (?P<branch>.*)\n", remote_info).group(
                    "branch"
                )
            repo.create_head(
                branch, origin.refs[branch]
            )  # create a local branch default from remote HEAD symref
            repo.heads[branch].set_tracking_branch(
                origin.refs[branch]
            )  # set the local branch to track the remote default branch
            repo.heads[branch].checkout()  # checkout the default branch to working tree
        except git.exc.GitCommandError as exc:
            raise RuntimeError("Failed to import from git:\n {}".format(str(exc)))

        # Tale is ready to be built
        tale = Tale().load(tale["_id"], user=user)  # Refresh state
        tale["status"] = TaleStatus.READY
        tale = Tale().updateTale(tale)

        # 4. Wait for container to show up
        if spawn:
            instance = Instance().createInstance(tale, user, token, spawn=spawn)
            progressCurrent += 1
            jobModel.updateJob(
                job,
                status=JobStatus.RUNNING,
                log="Waiting for a Tale container",
                progressTotal=progressTotal,
                progressCurrent=progressCurrent,
                progressMessage="Waiting for a Tale container",
            )

            sleep_step = 5
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

    except Exception as exc:
        dot_git = os.path.join(workspace["fsPath"], ".git")
        if not has_dot_git_already and os.path.isdir(dot_git):
            shutil.rmtree(dot_git, ignore_errors=True)
        if change_status:
            tale = Tale().load(tale["_id"], user=user)  # Refresh state
            tale["status"] = TaleStatus.ERROR
            tale = Tale().updateTale(tale)
        jobModel.updateJob(
            job,
            progressTotal=progressTotal,
            progressCurrent=progressTotal,
            progressMessage="Task failed",
            status=JobStatus.ERROR,
            log=str(exc),
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
