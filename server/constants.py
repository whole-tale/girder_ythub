#!/usr/bin/env python
# -*- coding: utf-8 -*-

from girder import events


API_VERSION = "2.1"
CATALOG_NAME = "WholeTale Catalog"
WORKSPACE_NAME = "WholeTale Workspaces"
DATADIRS_NAME = "WholeTale Data Mountpoints"
SCRIPTDIRS_NAME = "WholeTale Narrative"


class HarvesterType:
    """
    All possible data harverster implementation types.
    """

    DATAONE = 0


class PluginSettings:
    INSTANCE_CAP = "wholetale.instance_cap"
    DATAVERSE_URL = "wholetale.dataverse_url"
    DATAVERSE_EXTRA_HOSTS = "wholetale.dataverse_extra_hosts"
    EXTERNAL_AUTH_PROVIDERS = "wholetale.external_auth_providers"
    EXTERNAL_APIKEY_GROUPS = "wholetale.external_apikey_groups"
    ZENODO_EXTRA_HOSTS = "wholetale.zenodo_extra_hosts"


class SettingDefault:
    defaults = {
        PluginSettings.INSTANCE_CAP: 2,
        PluginSettings.DATAVERSE_URL: (
            "https://services.dataverse.harvard.edu/miniverse/map/installations-json"
        ),
        PluginSettings.DATAVERSE_EXTRA_HOSTS: [],
        PluginSettings.EXTERNAL_AUTH_PROVIDERS: [
            {
                "name": "orcid",
                "logo": "",
                "fullName": "ORCID",
                "tags": ["publish"],
                "url": "",
                "type": "bearer",
                "state": "unauthorized",
            },
            {
                "name": "zenodo",
                "logo": "",
                "fullName": "Zenodo",
                "tags": ["data", "publish"],
                "url": "",
                "type": "apikey",
                "docs_href": "https://zenodo.org/account/settings/applications/tokens/new/",
                "targets": [],
            },
            {
                "name": "dataverse",
                "logo": "",
                "fullName": "Dataverse",
                "tags": ["data", "publish"],
                "url": "",
                "type": "apikey",
                "docs_href": "http://guides.dataverse.org/en/latest/api/auth.html",
                "targets": [],
            },
            {
                "name": "dataonestage2",
                "logo": "",
                "fullName": "DataONE Stage 2 CN",
                "tags": ["publish"],
                "url": "",
                "type": "dataone",
                "state": "unauthorized",
            },
        ],
        PluginSettings.EXTERNAL_APIKEY_GROUPS: [
            {"name": "zenodo", "targets": ["sandbox.zenodo.org", "zenodo.org"]},
            {
                "name": "dataverse",
                "targets": [
                    "dev2.dataverse.org",
                    "dataverse.harvard.org",
                    "demo.dataverse.org",
                ],
            },
        ],
        PluginSettings.ZENODO_EXTRA_HOSTS: [],
    }


# Constants representing the setting keys for this plugin
class InstanceStatus(object):
    LAUNCHING = 0
    RUNNING = 1
    ERROR = 2
    DELETING = 3

    @staticmethod
    def isValid(status):
        event = events.trigger("instance.status.validate", info=status)

        if event.defaultPrevented and len(event.responses):
            return event.responses[-1]

        return status in (
            InstanceStatus.RUNNING,
            InstanceStatus.ERROR,
            InstanceStatus.LAUNCHING,
            InstanceStatus.DELETING,
        )


class ImageStatus(object):
    INVALID = 0
    UNAVAILABLE = 1
    BUILDING = 2
    AVAILABLE = 3

    @staticmethod
    def isValid(status):
        event = events.trigger("wholetale.image.status.validate", info=status)

        if event.defaultPrevented and len(event.responses):
            return event.responses[-1]

        return status in (
            ImageStatus.INVALID,
            ImageStatus.UNAVAILABLE,
            ImageStatus.BUILDING,
            ImageStatus.AVAILABLE,
        )


class TaleStatus(object):
    PREPARING = 0
    READY = 1
    ERROR = 2
