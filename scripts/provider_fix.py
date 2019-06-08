#!/usr/bin/env girder-shell
# -*- coding: utf-8 -*-

"""

Example:

    $ ./provider_fix.py

"""

from girder.models.folder import Folder
from girder.models.item import Item
from girder.plugins.wholetale.utils import getOrCreateRootFolder
from girder.plugins.wholetale.constants import CATALOG_NAME


CAT_ROOT = getOrCreateRootFolder(CATALOG_NAME)


def fix_provider(folder, provider):
    for item in Folder().childItems(folder):
        if 'meta' not in item:
            item['meta'] = {}
        item['meta']['provider'] = provider
        Item().save(item)

    for child_folder in Folder().childFolders(folder, parentType='folder', force=True):
        if 'meta' not in child_folder:
            child_folder['meta'] = {}
        child_folder['meta']['provider'] = provider
        fix_provider(child_folder, provider)


for folder in Folder().childFolders(CAT_ROOT, parentType='folder', force=True):
    provider = folder['meta']['provider']
    fix_provider(folder, provider)
