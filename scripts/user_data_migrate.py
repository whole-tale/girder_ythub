#!/usr/bin/env girder-shell
# -*- coding: utf-8 -*-

"""Migrate user registered data from folder to user model.

This script should be used to migrate user registered data from /user/{id}/Data
to user['myData'] structure. See https://github.com/whole-tale/girder_wholetale/pull/205

Example:

    $ ./user_data_migrate.py

"""

import pprint
from girder.models.folder import Folder
from girder.models.item import Item
from girder.models.user import User
from girder.plugins.wholetale.models.tale import Tale
from girder.plugins.wholetale.utils import getOrCreateRootFolder
from girder.plugins.wholetale.constants import CATALOG_NAME

CAT_ROOT = getOrCreateRootFolder(CATALOG_NAME)

for user in list(User().find()):
    data_folder = Folder().findOne({
        'parentId': user['_id'],
        'parentCollection': 'user',
        'name': 'Data'
    })
    my_data = []
    if data_folder:
        for folder in Folder().childFolders(data_folder, parentType='folder', force=True):
            if 'meta' in folder:
                orig_folder = Folder().findOne({
                    'parentId': CAT_ROOT['_id'],
                    'meta.identifier': folder['meta']['identifier']
                })
                if not orig_folder:
                    print("Stray folder in user/{}/Data".format(user['login']))
                    print(folder['meta']['identifier'])
                else:
                    my_data.append(orig_folder['_id'])

        for item in Folder().childItems(data_folder):
            if 'copyOfItem' not in item:
                print("Stray item in user/{}/Data".format(user['login']))
                if 'linkUrl' in item:
                    print("Something is seriously wrong")
                else:
                    print("/user/{}/Data/{} needs to be copied to Home".format(
                        user['login'], item['name']))
            else:
                orig_item = Item().load(item['copyOfItem'], force=True)
                if orig_item['folderId'] != CAT_ROOT['_id']:
                    print("**Stray item in user/{}/Data".format(user['login']))
                else:
                    my_data.append(orig_item['_id'])
    else:
        print('User "{}" does not have a data_folder...'.format(user['login']))
    user_data = set(user.get('myData', []))
    user['myData'] = list(user_data.union(set(my_data)))
    user = User().save(user)
