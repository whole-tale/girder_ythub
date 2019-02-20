#!/usr/bin/env girder-shell
# -*- coding: utf-8 -*-

"""Ensure that Tales' ACLs match Tale's folders ACLs.

See https://github.com/whole-tale/girder_wholetale/pull/243

Example:

    $ ./tale_acls_fix.py

"""

from girder.models.folder import Folder
from girder.models.user import User
from girder.plugins.wholetale.models.tale import Tale


for tale in list(Tale().find()):
    creator = User().load(tale['creatorId'], force=True)
    access = Tale().getFullAccessList(tale)
    currentFlags = tale.get('publicFlags', [])
    if 'workspaceId' not in tale:
        workspace = Tale().createWorkspace(tale, creator=creator)
        tale['workspaceId'] = workspace['_id']
        tale = Tale().save(tale)
    else:
        workspace = Folder().load(tale['workspaceId'], force=True)
        workspace = Folder().setAccessList(
            workspace, access, user=creator, save=True, force=True, recurse=True,
            setPublic=tale['public'], publicFlags=currentFlags)

    if 'narrativeId' not in tale:
        narrative_folder = Tale().createNarrativeFolder(
            tale, creator=creator, default=not bool(tale.get('narrative', [])))
        tale['narrativeId'] = narrative_folder['_id']
        tale = Tale().save(tale)
    else:
        narrative_folder = Folder().load(tale['narrativeId'], force=True)
        if narrative_folder['name'] != 'default':
            narrative_folder = Folder().setAccessList(
                narrative_folder, access, user=creator, save=True, force=True, recurse=True,
                setPublic=tale['public'], publicFlags=currentFlags)
    # 'folderId' is obsolete ignore it.
