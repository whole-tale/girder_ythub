#!/usr/bin/env python
# -*- coding: utf-8 -*-
import cherrypy
import json
import tempfile
import textwrap
import time
import zipfile

from girder import events
from girder.api import access
from girder.api.rest import iterBody
from girder.api.docs import addModel
from girder.api.describe import Description, autoDescribeRoute
from girder.api.rest import Resource, filtermodel, RestException,\
    setResponseHeader, setContentDisposition

from girder.constants import AccessType, SortDir, TokenScope
from girder.utility import assetstore_utilities
from girder.utility.path import getResourcePath
from girder.utility.progress import ProgressContext
from girder.models.assetstore import Assetstore
from girder.models.folder import Folder
from girder.models.token import Token
from girder.models.setting import Setting
from girder.plugins.jobs.models.job import Job
from girder.plugins.jobs.constants import REST_CREATE_JOB_TOKEN_SCOPE
from gwvolman.tasks import import_tale, publish

from girder.plugins.jobs.constants import JobStatus

from ..schema.tale import taleModel as taleSchema
from ..models.tale import Tale as taleModel
from ..models.image import Image as imageModel
from ..lib import pids_to_entities, IMPORT_PROVIDERS
from ..lib.dataone import DataONELocations  # TODO: get rid of it
from ..lib.manifest import Manifest
from ..lib.exporters.bag import BagTaleExporter
from ..lib.exporters.native import NativeTaleExporter

from girder.plugins.worker import getCeleryApp

from ..constants import ImageStatus, TaleStatus, PluginSettings


addModel('tale', taleSchema, resources='tale')


class Tale(Resource):

    def __init__(self):
        super(Tale, self).__init__()
        self.resourceName = 'tale'
        self._model = taleModel()

        self.route('GET', (), self.listTales)
        self.route('GET', (':id',), self.getTale)
        self.route('PUT', (':id',), self.updateTale)
        self.route('POST', ('import', ), self.createTaleFromDataset)
        self.route('POST', (), self.createTale)
        self.route('POST', (':id', 'copy'), self.copyTale)
        self.route('DELETE', (':id',), self.deleteTale)
        self.route('GET', (':id', 'access'), self.getTaleAccess)
        self.route('PUT', (':id', 'access'), self.updateTaleAccess)
        self.route('GET', (':id', 'export'), self.exportTale)
        self.route('GET', (':id', 'manifest'), self.generateManifest)
        self.route('PUT', (':id', 'build'), self.buildImage)
        self.route('PUT', (':id', 'publish'), self.publishTale)

    @access.public
    @filtermodel(model='tale', plugin='wholetale')
    @autoDescribeRoute(
        Description('Return all the tales accessible to the user')
        .param('text', ('Perform a full text search for Tale with a matching '
                        'title or description.'), required=False)
        .param('userId', "The ID of the tale's creator.", required=False)
        .param('imageId', "The ID of the tale's image.", required=False)
        .param(
            'level',
            'The minimum access level to the Tale.',
            required=False,
            dataType='integer',
            default=AccessType.READ,
            enum=[AccessType.NONE, AccessType.READ, AccessType.WRITE, AccessType.ADMIN],
        )
        .pagingParams(defaultSort='title',
                      defaultSortDir=SortDir.DESCENDING)
        .responseClass('tale', array=True)
    )
    def listTales(self, text, userId, imageId, level, limit, offset, sort,
                  params):
        currentUser = self.getCurrentUser()
        image = None
        if imageId:
            image = imageModel().load(imageId, user=currentUser, level=AccessType.READ, exc=True)

        creator = None
        if userId:
            creator = self.model('user').load(userId, force=True, exc=True)

        if text:
            filters = {}
            if creator:
                filters['creatorId'] = creator['_id']
            if image:
                filters['imageId'] = image['_id']
            return list(self._model.textSearch(
                text, user=currentUser, filters=filters,
                limit=limit, offset=offset, sort=sort, level=level))
        else:
            return list(self._model.list(
                user=creator, image=image, limit=limit, offset=offset,
                sort=sort, currentUser=currentUser, level=level))

    @access.public
    @filtermodel(model='tale', plugin='wholetale')
    @autoDescribeRoute(
        Description('Get a tale by ID.')
        .modelParam('id', model='tale', plugin='wholetale', level=AccessType.READ)
        .responseClass('tale')
        .errorResponse('ID was invalid.')
        .errorResponse('Read access was denied for the tale.', 403)
    )
    def getTale(self, tale, params):
        return tale

    @access.user
    @filtermodel(model='tale', plugin='wholetale')
    @autoDescribeRoute(
        Description('Update an existing tale.')
        .modelParam('id', model='tale', plugin='wholetale',
                    level=AccessType.WRITE, destName='taleObj')
        .jsonParam('tale', 'Updated tale', paramType='body', schema=taleSchema,
                   dataType='tale')
        .responseClass('tale')
        .errorResponse('ID was invalid.')
        .errorResponse('Admin access was denied for the tale.', 403)
    )
    def updateTale(self, taleObj, tale, params):
        is_public = tale.pop('public')

        update_citations = {_['itemId'] for _ in tale['dataSet']} ^ {
            _['itemId'] for _ in taleObj['dataSet']
        }  # XOR between new and old dataSet

        for keyword in self._model.modifiableFields:
            try:
                if keyword == 'imageId':
                    image = imageModel().load(
                        tale['imageId'], user=self.getCurrentUser(),
                        level=AccessType.READ, exc=True)
                    taleObj['imageId'] = image['_id']
                    continue
                taleObj[keyword] = tale.pop(keyword)
            except KeyError:
                pass
        taleObj = self._model.updateTale(taleObj)

        was_public = taleObj.get('public', False)
        if was_public != is_public:
            access = self._model.getFullAccessList(taleObj)
            user = self.getCurrentUser()
            taleObj = self._model.setAccessList(
                taleObj, access, save=True, user=user, setPublic=is_public)

        if update_citations:
            eventParams = {
                'tale': taleObj,
                'user': self.getCurrentUser(),
            }
            event = events.trigger('tale.update_citation', eventParams)
            if len(event.responses):
                taleObj = self._model.updateTale(event.responses[-1])
        return taleObj

    @access.user
    @autoDescribeRoute(
        Description('Delete an existing tale.')
        .modelParam('id', model='tale', plugin='wholetale', level=AccessType.ADMIN)
        .param('progress', 'Whether to record progress on this task.',
               required=False, dataType='boolean', default=False)
        .errorResponse('ID was invalid.')
        .errorResponse('Admin access was denied for the tale.', 403)
    )
    def deleteTale(self, tale, progress):
        user = self.getCurrentUser()
        workspace = Folder().load(
            tale['workspaceId'], user=user, level=AccessType.ADMIN)
        with ProgressContext(
                progress, user=user,
                title='Deleting workspace of {title}'.format(**tale),
                message='Calculating folder size...') as ctx:
            if progress:
                ctx.update(total=Folder().subtreeCount(workspace))
            Folder().remove(workspace, progress=ctx)
        self._model.remove(tale)

    @access.user
    @filtermodel(model='tale', plugin='wholetale')
    @autoDescribeRoute(
        Description('Create a new tale from an external dataset.')
        .notes('Currently, this task only handles importing raw data. '
               'A serialized Tale can be sent as the body of the request using an '
               'appropriate content-type and with the other parameters as part '
               'of the query string. The file will be stored in a temporary '
               'space. However, it is not currently being processed in any '
               'way.')
        .param('imageId', "The ID of the tale's image.", required=False)
        .param('url', 'External dataset identifier.', required=False)
        .param('spawn', 'If false, create only Tale object without a corresponding '
                        'Instance.',
               default=True, required=False, dataType='boolean')
        .param('asTale', 'If True, assume that external dataset is a Tale.',
               default=False, required=False, dataType='boolean')
        .jsonParam('lookupKwargs', 'Optional keyword arguments passed to '
                   'GET /repository/lookup', requireObject=True, required=False)
        .jsonParam('taleKwargs', 'Optional keyword arguments passed to POST /tale',
                   required=False, default={})
        .responseClass('tale')
        .errorResponse('You are not authorized to create tales.', 403)
    )
    def createTaleFromDataset(self, imageId, url, spawn, asTale, lookupKwargs, taleKwargs):
        user = self.getCurrentUser()
        token = Token().createToken(
            user=user,
            days=0.5,
            scope=(TokenScope.USER_AUTH, REST_CREATE_JOB_TOKEN_SCOPE)
        )

        if cherrypy.request.headers.get('Content-Type') == 'application/zip':
            tale = taleModel().createTaleFromStream(iterBody, user=user, token=token)
        else:
            if not url:
                msg = (
                    "You need to provide either : "
                    " 1) a zipfile with an exported Tale or "
                    " 2) a url to a Tale or "
                    " 3) both 'imageId' and 'url' parameters."
                )
                raise RestException(msg)

            try:
                lookupKwargs['dataId'] = [url]
            except TypeError:
                lookupKwargs = dict(dataId=[url])

            dataMap = pids_to_entities(
                lookupKwargs["dataId"],
                user=user,
                base_url=lookupKwargs.get("base_url", DataONELocations.prod_cn),
                lookup=True
            )[0]
            if dataMap["tale"]:
                provider = IMPORT_PROVIDERS.providerMap[dataMap["repository"]]
                tale = provider.import_tale(dataMap["dataId"], user)
                return tale

            if "title" not in taleKwargs:
                long_name = dataMap["name"]
                long_name = long_name.replace('-', ' ').replace('_', ' ')
                shortened_name = textwrap.shorten(text=long_name, width=30)
                taleKwargs["title"] = "A Tale for \"{}\"".format(shortened_name)

            if not (imageId or url):
                msg = (
                    "You need to provide either a zipfile with an exported Tale or "
                    " both 'imageId' and 'url' parameters."
                )
                raise RestException(msg)

            image = imageModel().load(imageId, user=user, level=AccessType.READ,
                                      exc=True)

            if "icon" not in taleKwargs:
                taleKwargs["icon"] = image.get(
                    "icon",
                    (
                        "https://raw.githubusercontent.com/"
                        "whole-tale/dashboard/master/public/"
                        "images/whole_tale_logo.png"
                    ),
                )

            if "illustration" not in taleKwargs:
                taleKwargs["illustration"] = (
                    "https://raw.githubusercontent.com/"
                    "whole-tale/dashboard/master/public/"
                    "images/demo-graph2.jpg"
                )

            tale = taleModel().createTale(
                image,
                [],
                creator=user,
                category="science",
                save=True,
                public=False,
                status=TaleStatus.PREPARING,
                **taleKwargs
            )

            if asTale:
                job = Job().createLocalJob(
                    title="Import Tale from external dataset",
                    user=user,
                    type="wholetale.import_binder",
                    public=False,
                    async=True,
                    module="girder.plugins.wholetale.tasks.import_binder",
                    args=(lookupKwargs,),
                    kwargs={"user": user, "tale": tale, "spawn": spawn},
                )
                Job().scheduleJob(job)
            else:
                import_tale.delay(
                    lookupKwargs, tale, spawn=spawn,
                    girder_client_token=str(token['_id'])
                )
        return tale

    @access.user
    @autoDescribeRoute(
        Description('Create a new tale.')
        .jsonParam('tale', 'A new tale', paramType='body', schema=taleSchema,
                   dataType='tale')
        .responseClass('tale')
        .errorResponse('You are not authorized to create tales.', 403)
    )
    def createTale(self, tale, params):

        user = self.getCurrentUser()
        if 'instanceId' in tale:
            # check if instance exists
            # save disk state to a new folder
            # save config
            # create a tale
            raise RestException('Not implemented yet')
        else:
            image = self.model('image', 'wholetale').load(
                tale['imageId'], user=user, level=AccessType.READ, exc=True)
            default_author = ' '.join((user['firstName'], user['lastName']))
            return self._model.createTale(
                image, tale['dataSet'], creator=user, save=True,
                title=tale.get('title'), description=tale.get('description'),
                public=tale.get('public'), config=tale.get('config'),
                icon=image.get('icon', ('https://raw.githubusercontent.com/'
                                        'whole-tale/dashboard/master/public/'
                                        'images/whole_tale_logo.png')),
                illustration=tale.get(
                    'illustration', ('https://raw.githubusercontent.com/'
                                     'whole-tale/dashboard/master/public/'
                                     'images/demo-graph2.jpg')),
                authors=tale.get('authors', default_author),
                category=tale.get('category', 'science'),
                narrative=tale.get('narrative'),
                licenseSPDX=tale.get('licenseSPDX')
            )

    @access.user(scope=TokenScope.DATA_OWN)
    @autoDescribeRoute(
        Description('Get the access control list for a tale')
        .modelParam('id', model='tale', plugin='wholetale', level=AccessType.ADMIN)
        .errorResponse('ID was invalid.')
        .errorResponse('Admin access was denied for the tale.', 403)
    )
    def getTaleAccess(self, tale):
        return self._model.getFullAccessList(tale)

    @access.user(scope=TokenScope.DATA_OWN)
    @autoDescribeRoute(
        Description('Update the access control list for a tale.')
        .modelParam('id', model='tale', plugin='wholetale', level=AccessType.ADMIN)
        .jsonParam('access', 'The JSON-encoded access control list.', requireObject=True)
        .jsonParam('publicFlags', 'JSON list of public access flags.', requireArray=True,
                   required=False)
        .param('public', 'Whether the tale should be publicly visible.', dataType='boolean',
               required=False)
        .errorResponse('ID was invalid.')
        .errorResponse('Admin access was denied for the tale.', 403)
    )
    def updateTaleAccess(self, tale, access, publicFlags, public):
        user = self.getCurrentUser()
        return self._model.setAccessList(
            tale, access, save=True, user=user, setPublic=public, publicFlags=publicFlags)

    @access.user
    @autoDescribeRoute(
        Description('Export a tale as a zipfile')
        .modelParam('id', model='tale', plugin='wholetale', level=AccessType.READ)
        .param('taleFormat', 'Format of the exported Tale', required=False,
               enum=['bagit', 'native'], strip=True, default='native')
        .responseClass('tale')
        .produces('application/zip')
        .errorResponse('ID was invalid.', 404)
        .errorResponse('You are not authorized to export this tale.', 403)
    )
    def exportTale(self, tale, taleFormat):
        user = self.getCurrentUser()
        zip_name = str(tale['_id'])

        if taleFormat == 'bagit':
            exporter = BagTaleExporter(tale, user, expand_folders=True)
        elif taleFormat == 'native':
            exporter = NativeTaleExporter(tale, user)

        setResponseHeader('Content-Type', 'application/zip')
        setContentDisposition(zip_name + '.zip')
        return exporter.stream

    @access.public
    @autoDescribeRoute(
        Description('Generate the Tale manifest')
        .modelParam('id', model='tale', plugin='wholetale', level=AccessType.READ)
        .param('expandFolders', "If True, folders in Tale's dataSet are recursively "
               "expanded to items in the 'aggregates' section",
               required=False, dataType='boolean', default=False)
        .errorResponse('ID was invalid.')
    )
    def generateManifest(self, tale, expandFolders):
        """
        Creates a manifest document and returns the contents.
        :param tale: The Tale whose information is being used
        :param itemIds: An optional list of items to include in the manifest
        :return: A JSON structure representing the Tale
        """

        user = self.getCurrentUser()
        manifest_doc = Manifest(tale, user, expand_folders=expandFolders)
        return manifest_doc.manifest

    @access.user
    @autoDescribeRoute(
        Description('Build the image for the Tale')
        .modelParam('id', model='tale', plugin='wholetale', level=AccessType.WRITE,
                    description='The ID of the Tale.')
        .param('force', 'If true, force build regardless of workspace changes',
               default=False, required=False, dataType='boolean')
        .errorResponse('ID was invalid.')
        .errorResponse('Admin access was denied for the tale.', 403)
    )
    def buildImage(self, tale, force):
        user = self.getCurrentUser()
        return self._model.buildImage(tale, user, force=force)

    def updateBuildStatus(self, event):
        """
        Event handler that updates the Tale object based on the build_tale_image task.
        """
        job = event.info['job']
        if job['title'] == 'Build Tale Image' and job.get('status') is not None:
            status = int(job['status'])
            tale = self.model('tale', 'wholetale').load(
                job['args'][0], force=True)

            if 'imageInfo' not in tale:
                tale['imageInfo'] = {}

            # Store the previous status, if present.
            previousStatus = -1
            try:
                previousStatus = tale['imageInfo']['status']
            except KeyError:
                pass

            if status == JobStatus.SUCCESS:
                result = getCeleryApp().AsyncResult(job['celeryTaskId']).get()
                tale['imageInfo']['digest'] = result['image_digest']
                tale['imageInfo']['repo2docker_version'] = result['repo2docker_version']
                tale['imageInfo']['last_build'] = result['last_build']
                tale['imageInfo']['status'] = ImageStatus.AVAILABLE
            elif status == JobStatus.ERROR:
                tale['imageInfo']['status'] = ImageStatus.INVALID
            elif status in (JobStatus.QUEUED, JobStatus.RUNNING):
                tale['imageInfo']['jobId'] = job['_id']
                tale['imageInfo']['status'] = ImageStatus.BUILDING

            # If the status changed, save the object
            if 'status' in tale['imageInfo'] and tale['imageInfo']['status'] != previousStatus:
                self.model('tale', 'wholetale').updateTale(tale)

    def updateWorkspaceModTime(self, event):
        """
        Handler for model.file.save, model.file.save.created and
        model.file.remove events When files in a workspace are modified or
        deleted, update the associated Tale with a workspaceModified time.
        This is used to determine whether to rebuild or not.
        """

        # Get the path
        path = getResourcePath('file', event.info, force=True)

        # If the file is in a workspace, parse the Tale ID
        # e.g., "/collection/WholeTale Workspaces/
        #  WholeTale Workspaces/5c848784912a470001e9545d/file.txt"
        if path.startswith('/collection/WholeTale Workspaces/WholeTale Workspaces'):
            elems = path.split('/')
            taleId = elems[4]
            tale = self.model('tale', 'wholetale').load(taleId, force=True)
            tale['workspaceModified'] = int(time.time())
            self.model('tale', 'wholetale').save(tale)

    @access.user
    @autoDescribeRoute(
        Description('Copy a tale.')
        .modelParam('id', model='tale', plugin='wholetale', level=AccessType.READ)
        .responseClass('tale')
        .errorResponse('ID was invalid.')
        .errorResponse('You are not authorized to copy this tale.', 403)
    )
    @filtermodel(model='tale', plugin='wholetale')
    def copyTale(self, tale):
        user = self.getCurrentUser()
        image = self.model('image', 'wholetale').load(
            tale['imageId'], user=user, level=AccessType.READ, exc=True)
        default_author = ' '.join((user['firstName'], user['lastName']))
        new_tale = self._model.createTale(
            image, tale['dataSet'], creator=user, save=True,
            title=tale.get('title'), description=tale.get('description'),
            public=False, config=tale.get('config'),
            icon=image.get('icon', ('https://raw.githubusercontent.com/'
                                    'whole-tale/dashboard/master/public/'
                                    'images/whole_tale_logo.png')),
            illustration=tale.get(
                'illustration', ('https://raw.githubusercontent.com/'
                                 'whole-tale/dashboard/master/public/'
                                 'images/demo-graph2.jpg')),
            authors=tale.get('authors', default_author),
            category=tale.get('category', 'science'),
            narrative=tale.get('narrative'),
            licenseSPDX=tale.get('licenseSPDX'),
            status=TaleStatus.PREPARING,
        )
        new_tale['copyOfTale'] = tale['_id']
        new_tale = self._model.save(new_tale)
        # asynchronously copy the workspace of a source Tale
        tale_workspaceId = self._model.createWorkspace(tale)['_id']
        new_tale_workspaceId = self._model.createWorkspace(new_tale)['_id']
        job = Job().createLocalJob(
            title='Copy "{title}" workspace'.format(**tale), user=user,
            type='wholetale.copy_workspace', public=False, async=True,
            module='girder.plugins.wholetale.tasks.copy_workspace',
            args=(tale_workspaceId, new_tale_workspaceId),
            kwargs={'user': user, 'tale': new_tale}
        )
        Job().scheduleJob(job)
        return new_tale

    @staticmethod
    def _extractZipPayload():
        # TODO: Move assetstore type to wholetale.
        assetstore = next((_ for _ in Assetstore().list() if _['type'] == 101), None)
        if assetstore:
            adapter = assetstore_utilities.getAssetstoreAdapter(assetstore)
            tempDir = adapter.tempDir
        else:
            tempDir = None

        with tempfile.NamedTemporaryFile(dir=tempDir) as fp:
            for chunk in iterBody(2 * 1024 ** 3):
                fp.write(chunk)
            fp.seek(0)
            if not zipfile.is_zipfile(fp):
                raise RestException("Provided file is not a zipfile")

            with zipfile.ZipFile(fp) as z:
                manifest_file = next(
                    (_ for _ in z.namelist() if _.endswith('manifest.json')),
                    None
                )
                if not manifest_file:
                    raise RestException("Provided file doesn't contain a Tale manifest")

                try:
                    manifest = json.loads(z.read(manifest_file).decode())
                    # TODO: is there a better check?
                    manifest['@id'].startswith('https://data.wholetale.org')
                except Exception as e:
                    raise RestException(
                        "Couldn't read manifest.json or not a Tale: {}".format(str(e))
                    )

                env_file = next(
                    (_ for _ in z.namelist() if _.endswith("environment.json")),
                    None
                )
                try:
                    environment = json.loads(z.read(env_file).decode())
                except Exception as e:
                    raise RestException(
                        "Couldn't read environment.json or not a Tale: {}".format(str(e))
                    )

                # Extract files to tmp on workspace assetstore
                temp_dir = tempfile.mkdtemp(dir=tempDir)
                # In theory malicious content like: abs path for a member, or relative path with
                # ../.. etc., is taken care of by zipfile.extractall, but in the end we're still
                # unzipping an untrusted content. What could possibly go wrong...?
                z.extractall(path=temp_dir)
        return temp_dir, manifest_file, manifest, environment

    @access.user(scope=TokenScope.DATA_WRITE)
    @filtermodel(model=Job)
    @autoDescribeRoute(
        Description("Publish a Tale to a data repository")
        .modelParam(
            "id",
            description="The ID of the tale that is going to be published.",
            model="tale",
            plugin="wholetale",
            level=AccessType.ADMIN,
        )
        .param(
            "repository",
            description="The URL to a repository, where tale is going to be published.\n"
            "Example: 'https://dev.nceas.ucsb.edu/knb/d1/mn', 'sandbox.zenodo.org'",
            required=True,
        )
    )
    def publishTale(self, tale, repository):
        user = self.getCurrentUser()
        publishers = {
            entry["repository"]: entry["auth_provider"]
            for entry in Setting().get(PluginSettings.PUBLISHER_REPOS)
        }

        try:
            publisher = publishers[repository]
        except KeyError:
            raise RestException("Unknown publisher repository ({})".format(repository))

        if publisher.startswith("dataone"):
            key = "provider"  # Dataone
            value = publisher
        else:
            key = "resource_server"
            value = repository

        token = next(
            (_ for _ in user.get("otherTokens", []) if _.get(key) == value), None
        )
        if not token:
            raise RestException("Missing a token for publisher ({}).".format(publisher))

        girder_token = Token().createToken(user=user, days=0.5)

        publishTask = publish.delay(
            str(tale["_id"]),
            token,
            repository=repository,
            girder_client_token=str(girder_token["_id"]),
        )
        return publishTask.job
