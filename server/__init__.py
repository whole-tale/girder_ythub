#!/usr/bin/env python
# -*- coding: utf-8 -*-

import base64
import copy
import datetime
import jsonschema
import os
import six
import validators

from girder import events, logprint, logger
from girder.api import access
from girder.api.describe import Description, describeRoute, autoDescribeRoute
from girder.api.rest import \
    boundHandler, loadmodel, RestException
from girder.constants import AccessType, TokenScope
from girder.exceptions import GirderException
from girder.models.model_base import ValidationException
from girder.models.notification import Notification, ProgressState
from girder.models.user import User
from girder.plugins.jobs.constants import JobStatus
from girder.plugins.jobs.models.job import Job as JobModel
from girder.plugins.worker import getCeleryApp
from girder.utility import assetstore_utilities, setting_utilities
from girder.utility.model_importer import ModelImporter

from .constants import PluginSettings, SettingDefault
from .rest.account import Account
from .rest.dataset import Dataset
from .rest.image import Image
from .rest.integration import Integration
from .rest.repository import Repository
from .rest.harvester import listImportedData
from .rest.tale import Tale
from .rest.instance import Instance
from .rest.wholetale import wholeTale
from .rest.license import License
from .models.instance import finalizeInstance
from .schema.misc import (
    external_auth_providers_schema,
    external_apikey_groups_schema,
    repository_to_provider_schema,
)


@setting_utilities.validator(PluginSettings.PUBLISHER_REPOS)
def validatePublisherRepos(doc):
    try:
        jsonschema.validate(doc['value'], repository_to_provider_schema)
    except jsonschema.ValidationError as e:
        raise ValidationException('Invalid Repository to Auth Provider map: ' + str(e))


@setting_utilities.default(PluginSettings.PUBLISHER_REPOS)
def defaultPublisherRepos():
    return copy.deepcopy(
        SettingDefault.defaults[PluginSettings.PUBLISHER_REPOS]
    )


@setting_utilities.validator(PluginSettings.EXTERNAL_APIKEY_GROUPS)
def validateExternalApikeyGroups(doc):
    try:
        jsonschema.validate(doc['value'], external_apikey_groups_schema)
    except jsonschema.ValidationError as e:
        raise ValidationException('Invalid External Apikey Groups list: ' + str(e))


@setting_utilities.validator(PluginSettings.EXTERNAL_AUTH_PROVIDERS)
def validateOtherSettings(doc):
    try:
        jsonschema.validate(doc['value'], external_auth_providers_schema)
    except jsonschema.ValidationError as e:
        raise ValidationException('Invalid External Auth Providers list: ' + str(e))


@setting_utilities.default(PluginSettings.EXTERNAL_AUTH_PROVIDERS)
def defaultExternalAuthProviders():
    return copy.deepcopy(
        SettingDefault.defaults[PluginSettings.EXTERNAL_AUTH_PROVIDERS]
    )


@setting_utilities.default(PluginSettings.EXTERNAL_APIKEY_GROUPS)
def defaultExternalApikeyGroups():
    return copy.deepcopy(
        SettingDefault.defaults[PluginSettings.EXTERNAL_APIKEY_GROUPS]
    )


@setting_utilities.validator(PluginSettings.DATAVERSE_EXTRA_HOSTS)
def validateDataverseExtraHosts(doc):
    if not doc['value']:
        doc['value'] = defaultDataverseExtraHosts()
    if not isinstance(doc['value'], list):
        raise ValidationException('Dataverse extra hosts setting must be a list.', 'value')
    for url in doc['value']:
        if not validators.domain(url):
            raise ValidationException('Invalid domain in Dataverse extra hosts', 'value')


@setting_utilities.validator(PluginSettings.ZENODO_EXTRA_HOSTS)
def validateZenodoExtraHosts(doc):
    if not doc['value']:
        doc['value'] = defaultZenodoExtraHosts()
    if not isinstance(doc['value'], list):
        raise ValidationException('Zenodo extra hosts setting must be a list.', 'value')
    for url in doc['value']:
        if not validators.url(url):
            raise ValidationException('Invalid URL in Zenodo extra hosts', 'value')


@setting_utilities.validator(PluginSettings.INSTANCE_CAP)
def validateInstanceCap(doc):
    if not doc['value']:
        doc['value'] = defaultInstanceCap()
    try:
        int(doc['value'])
    except ValueError:
        raise ValidationException(
            'Instance Cap needs to be an integer.', 'value')


@setting_utilities.validator(PluginSettings.DATAVERSE_URL)
def validateDataverseURL(doc):
    if not doc['value']:
        doc['value'] = defaultDataverseURL()
    if not validators.url(doc['value']):
        raise ValidationException('Invalid Dataverse URL', 'value')


@setting_utilities.default(PluginSettings.INSTANCE_CAP)
def defaultInstanceCap():
    return SettingDefault.defaults[PluginSettings.INSTANCE_CAP]


@setting_utilities.default(PluginSettings.DATAVERSE_URL)
def defaultDataverseURL():
    return SettingDefault.defaults[PluginSettings.DATAVERSE_URL]


@setting_utilities.default(PluginSettings.DATAVERSE_EXTRA_HOSTS)
def defaultDataverseExtraHosts():
    return SettingDefault.defaults[PluginSettings.DATAVERSE_EXTRA_HOSTS]


@setting_utilities.default(PluginSettings.ZENODO_EXTRA_HOSTS)
def defaultZenodoExtraHosts():
    return SettingDefault.defaults[PluginSettings.ZENODO_EXTRA_HOSTS]


@access.public(scope=TokenScope.DATA_READ)
@loadmodel(model='folder', level=AccessType.READ)
@describeRoute(
    Description('List the content of a folder.')
    .param('id', 'The ID of the folder.', paramType='path')
    .errorResponse('ID was invalid.')
    .errorResponse('Read access was denied for the folder.', 403)
)
@boundHandler()
def listFolder(self, folder, params):
    user = self.getCurrentUser()
    folders = list(
        self.model('folder').childFolders(parentType='folder',
                                          parent=folder, user=user))

    files = []
    for item in self.model('folder').childItems(folder=folder):
        childFiles = list(self.model('item').childFiles(item))
        if len(childFiles) == 1:
            fileitem = childFiles[0]
            if 'imported' not in fileitem and \
                    fileitem.get('assetstoreId') is not None:
                try:
                    store = \
                        self.model('assetstore').load(fileitem['assetstoreId'])
                    adapter = assetstore_utilities.getAssetstoreAdapter(store)
                    fileitem["path"] = adapter.fullPath(fileitem)
                except (ValidationException, AttributeError):
                    pass
            files.append(fileitem)
        else:
            folders.append(item)
    return {'folders': folders, 'files': files}


@access.public(scope=TokenScope.DATA_READ)
@autoDescribeRoute(
    Description('Convert folder content into DM dataSet')
    .modelParam('id', 'The ID of the folder', model='folder',
                level=AccessType.READ)
)
@boundHandler()
def getDataSet(self, folder, params):
    modelFolder = self.model('folder')

    def _getPath(folder, user, path=''):
        dataSet = [
            {
                'itemId': item['_id'],
                'mountPoint': path + item['name'],
                '_modelType': 'item',
            }
            for item in modelFolder.childItems(folder=folder)
        ]
        for childFolder in modelFolder.childFolders(
                parentType='folder', parent=folder, user=user):
            dataSet += _getPath(childFolder, user,
                                path + childFolder['name'] + '/')
        return dataSet

    user = self.getCurrentUser()
    return _getPath(folder, user)


@access.public(scope=TokenScope.DATA_READ)
@loadmodel(model='item', level=AccessType.READ)
@describeRoute(
    Description('List the content of an item.')
    .param('id', 'The ID of the folder.', paramType='path')
    .errorResponse('ID was invalid.')
    .errorResponse('Read access was denied for the folder.', 403)
)
@boundHandler()
def listItem(self, item, params):
    files = []
    for fileitem in self.model('item').childFiles(item):
        if 'imported' not in fileitem and \
                fileitem.get('assetstoreId') is not None:
            try:
                store = \
                    self.model('assetstore').load(fileitem['assetstoreId'])
                adapter = assetstore_utilities.getAssetstoreAdapter(store)
                fileitem["path"] = adapter.fullPath(fileitem)
            except (ValidationException, AttributeError):
                pass
        files.append(fileitem)
    return {'folders': [], 'files': files}


@access.user
@describeRoute(
    Description('Update the user settings.')
    .errorResponse('Read access was denied.', 403)
)
@boundHandler()
def getUserMetadata(self, params):
    user = self.getCurrentUser()
    return user.get('meta', {})


@access.user
@describeRoute(
    Description('Get the user settings.')
    .param('body', 'A JSON object containing the metadata keys to add',
           paramType='body')
    .errorResponse('Write access was denied.', 403)
)
@boundHandler()
def setUserMetadata(self, params):
    user = self.getCurrentUser()
    metadata = self.getBodyJson()

    # Make sure we let user know if we can't accept a metadata key
    for k in metadata:
        if not len(k):
            raise RestException('Key names must be at least one character long.')
        if '.' in k or k[0] == '$':
            raise RestException('The key name %s must not contain a period '
                                'or begin with a dollar sign.' % k)

    if 'meta' not in user:
        user['meta'] = {}

    # Add new metadata to existing metadata
    user['meta'].update(six.viewitems(metadata))

    # Remove metadata fields that were set to null (use items in py3)
    toDelete = [k for k, v in six.viewitems(user['meta']) if v is None]
    for key in toDelete:
        del user['meta'][key]

    # Validate and save the user
    return self.model('user').save(user)


@access.user
@autoDescribeRoute(
    Description('Get a set of items and folders.')
    .jsonParam('resources', 'A JSON-encoded set of resources to get. Each type '
               'is a list of ids. Only folders and items may be specified. '
               'For example: {"item": [(item id 1), (item id2)], "folder": '
               '[(folder id 1)]}.', requireObject=True)
    .errorResponse('Unsupport or unknown resource type.')
    .errorResponse('Invalid resources format.')
    .errorResponse('Resource type not supported.')
    .errorResponse('No resources specified.')
    .errorResponse('Resource not found.')
    .errorResponse('ID was invalid.')
)
@boundHandler()
def listResources(self, resources, params):
    user = self.getCurrentUser()
    result = {}
    for kind in resources:
        try:
            model = self.model(kind)
            result[kind] = [
                model.load(id=id, user=user, level=AccessType.READ, exc=True)
                for id in resources[kind]]
        except ImportError:
            pass
    return result


def validateFileLink(event):
    # allow globus URLs
    doc = event.info
    if doc.get('assetstoreId') is None:
        if 'linkUrl' not in doc:
            raise ValidationException(
                'File must have either an assetstore ID or a link URL.',
                'linkUrl')
            doc['linkUrl'] = doc['linkUrl'].strip()

        if not doc['linkUrl'].startswith(('http:', 'https:', 'globus:')):
            raise ValidationException(
                'Linked file URL must start with http: or https: or globus:.',
                'linkUrl')
    if 'name' not in doc or not doc['name']:
        raise ValidationException('File name must not be empty.', 'name')

    doc['exts'] = [ext.lower() for ext in doc['name'].split('.')[1:]]
    event.preventDefault().addResponse(doc)


def updateNotification(event):
    """
    Update the Whole Tale task notification for a job, if present.
    """

    job = event.info['job']
    if job['progress'] and 'wt_notification_id' in job:
        state = JobStatus.toNotificationStatus(job['status'])
        notification = Notification().load(job['wt_notification_id'])

        state_changed = notification['data']['state'] != state
        message_changed = notification['data']['message'] != job['progress']['message']

        # Ignore duplicate events based on state and message content
        if not state_changed and not message_changed:
            return

        # For multi-job tasks, ignore success for intermediate events
        is_last = notification['data']['total'] == (notification['data']['current'])
        if state == ProgressState.SUCCESS and not is_last:
            return

        # Add job IDs to the resource
        if 'jobs' not in notification['data']['resource']:
            notification['data']['resource']['jobs'] = []

        if job['_id'] not in notification['data']['resource']['jobs']:
            notification['data']['resource']['jobs'].append(job['_id'])

        # If the state hasn't changed, increment. Otherwise keep previous current value.
        # Note, if expires parameter is not provided, updateProgress resets to 1 hour
        if not state_changed:
            Notification().updateProgress(
                notification, state=state,
                expires=notification['expires'],
                message=job['progress']['message'],
                increment=1,
                total=notification['data']['total'])
        else:
            Notification().updateProgress(
                notification, state=state,
                expires=notification['expires'],
                message=job['progress']['message'],
                current=notification['data']['current'],
                total=notification['data']['total'])


@access.user
@autoDescribeRoute(
    Description('Get output from celery job.')
    .modelParam('id', 'The ID of the job.', model=JobModel, force=True, includeLog=True)
    .errorResponse('ID was invalid.')
    .errorResponse('Read access was denied for the job.', 403)
)
@boundHandler()
def getJobResult(self, job):
    user = self.getCurrentUser()
    if not job.get('public', False):
        if user:
            JobModel().requireAccess(job, user, level=AccessType.READ)
        else:
            self.ensureTokenScopes('jobs.job_' + str(job['_id']))

    if 'result' in job:
        return job['result']

    celeryTaskId = job.get('celeryTaskId')
    if celeryTaskId is None:
        logger.warn(
            "Job '{}' doesn't have a Celery task id.".format(job['_id']))
        return
    if job['status'] != JobStatus.SUCCESS:
        logger.warn(
            "Job '{}' hasn't completed sucessfully.".format(job['_id']))
    asyncResult = getCeleryApp().AsyncResult(celeryTaskId)
    try:
        result = asyncResult.get()
    except Exception as ex:
        result = str(ex)
    return result


def store_other_globus_tokens(event):
    globus_token = event.info["token"]
    user = event.info["user"]
    user_tokens = user.get("otherTokens", [])
    for token in globus_token["other_tokens"]:
        for i, user_token in enumerate(user_tokens):
            if user_token["resource_server"] == token["resource_server"]:
                user_tokens[i].update(token)
                break
        else:
            user_tokens.append(token)
    user["otherTokens"] = user_tokens
    user["lastLogin"] = datetime.datetime.utcnow()
    User().save(user)


def load(info):
    info['apiRoot'].wholetale = wholeTale()
    info['apiRoot'].instance = Instance()
    tale = Tale()
    info['apiRoot'].tale = tale

    from girder.plugins.wholetale.models.tale import Tale as TaleModel
    from girder.plugins.wholetale.models.tale import _currentTaleFormat
    q = {
        '$or': [
            {'format': {'$exists': False}},
            {'format': {'$lt': _currentTaleFormat}}
        ]}
    for obj in TaleModel().find(q):
        try:
            TaleModel().save(obj, validate=True)
        except GirderException as exc:
            logprint(exc)

    info['apiRoot'].dataset = Dataset()
    info['apiRoot'].image = Image()
    events.bind('jobs.job.update.after', 'wholetale', tale.updateBuildStatus)
    events.bind('jobs.job.update.after', 'wholetale', finalizeInstance)
    events.bind('jobs.job.update.after', 'wholetale', updateNotification)
    events.bind('model.file.validate', 'wholetale', validateFileLink)
    events.bind('oauth.auth_callback.after', 'wholetale', store_other_globus_tokens)
    info['apiRoot'].account = Account()
    info['apiRoot'].repository = Repository()
    info['apiRoot'].license = License()
    info['apiRoot'].integration = Integration()
    info['apiRoot'].folder.route('GET', ('registered',), listImportedData)
    info['apiRoot'].folder.route('GET', (':id', 'listing'), listFolder)
    info['apiRoot'].folder.route('GET', (':id', 'dataset'), getDataSet)
    info['apiRoot'].job.route('GET', (':id', 'result'), getJobResult)
    info['apiRoot'].item.route('GET', (':id', 'listing'), listItem)
    info['apiRoot'].resource.route('GET', (), listResources)

    info['apiRoot'].user.route('PUT', ('settings',), setUserMetadata)
    info['apiRoot'].user.route('GET', ('settings',), getUserMetadata)
    ModelImporter.model('user').exposeFields(
        level=AccessType.WRITE, fields=('meta', 'myData', 'lastLogin'))
    ModelImporter.model('user').exposeFields(
        level=AccessType.ADMIN, fields=('otherTokens',))

    path_to_assets = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "web_client/extra/img",
    )
    for ext_provider in SettingDefault.defaults[PluginSettings.EXTERNAL_AUTH_PROVIDERS]:
        logo_path = os.path.join(path_to_assets, ext_provider["name"] + '_logo.jpg')
        print(logo_path)
        if os.path.isfile(logo_path):
            with open(logo_path, "rb") as image_file:
                ext_provider["logo"] = base64.b64encode(image_file.read()).decode()
