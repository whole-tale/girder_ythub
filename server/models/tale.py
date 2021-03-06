# -*- coding: utf-8 -*-

from bson.objectid import ObjectId
import datetime
import json
import jsonschema
import tempfile
import zipfile

from girder import events
from girder.constants import AccessType
from girder.exceptions import GirderException, ValidationException
from girder.models.assetstore import Assetstore
from girder.models.folder import Folder
from girder.models.item import Item
from girder.models.user import User
from girder.models.model_base import AccessControlledModel
from girder.models.token import Token
from girder.plugins.jobs.models.job import Job
from girder.utility import assetstore_utilities

from .image import Image as imageModel
from ..schema.misc import dataSetSchema
from ..constants import TaleStatus
from ..schema.misc import related_identifiers_schema
from ..utils import getOrCreateRootFolder, init_progress
from ..lib.license import WholeTaleLicense
from ..lib.manifest_parser import ManifestParser

from gwvolman.tasks import build_tale_image, BUILD_TALE_IMAGE_STEP_TOTAL


# Whenever the Tale object schema is modified (e.g. fields are added or
# removed) increase `_currentTaleFormat` to retroactively apply those
# changes to existing Tales.
_currentTaleFormat = 8


class Tale(AccessControlledModel):

    def initialize(self):
        self.name = 'tale'
        self.ensureIndices(('imageId', ([('imageId', 1)], {})))
        self.ensureTextIndex({
            'title': 10,
            'description': 1
        })
        self.modifiableFields = {
            'title', 'description', 'public', 'config', 'updated', 'authors',
            'category', 'icon', 'iframe', 'illustration', 'dataSet', 'licenseSPDX',
            'publishInfo', 'imageId', 'status', 'relatedIdentifiers',
        }
        self.exposeFields(
            level=AccessType.READ,
            fields=({'_id', 'imageId', 'creatorId', 'created',
                     'format', 'dataSet', 'licenseSPDX',
                     'imageInfo', 'publishInfo', 'dataSetCitation',
                     'copyOfTale'} | self.modifiableFields))

    @staticmethod
    def _validate_dataset(tale):
        try:
            jsonschema.validate(tale["dataSet"], dataSetSchema)
        except jsonschema.exceptions.ValidationError as exc:
            raise ValidationException(str(exc))

        creator = User().load(tale["creatorId"], force=True)
        for obj in tale["dataSet"]:
            if obj["_modelType"] == "folder":
                model = Folder()
            else:
                model = Item()
            model.load(
                obj["itemId"],
                level=AccessType.READ,
                user=creator,
                fields={},
                exc=True
            )

    @staticmethod
    def _validate_related_identifiers(tale):
        try:
            jsonschema.validate(tale["relatedIdentifiers"], related_identifiers_schema)
        except jsonschema.exceptions.ValidationError as exc:
            raise ValidationException(str(exc))

    def validate(self, tale):
        if 'status' not in tale:
            tale['status'] = TaleStatus.READY

        if 'iframe' not in tale:
            tale['iframe'] = False

        for array_key in (
            'publishInfo', 'dataSet', 'dataSetCitation', 'relatedIdentifiers', 'authors',
        ):
            if not isinstance(tale.get(array_key), list):
                tale[array_key] = []

        if 'licenseSPDX' not in tale:
            tale['licenseSPDX'] = WholeTaleLicense.default_spdx()
        tale_licenses = WholeTaleLicense()
        if tale['licenseSPDX'] not in tale_licenses.supported_spdxes():
            tale['licenseSPDX'] = WholeTaleLicense.default_spdx()

        if tale.get('config') is None:
            tale['config'] = {}

        if 'copyOfTale' not in tale:
            tale['copyOfTale'] = None

        tale['format'] = _currentTaleFormat

        self._validate_dataset(tale)
        self._validate_related_identifiers(tale)
        return tale

    def list(self, user=None, data=None, image=None, limit=0, offset=0,
             sort=None, currentUser=None, level=AccessType.READ):
        """
        List a page of jobs for a given user.

        :param user: The user who created the tale.
        :type user: dict or None
        :param data: The object array that's being used by the tale.
        :type data: dict or None
        :param image: The Image that's being used by the tale.
        :type image: dict or None
        :param limit: The page limit.
        :param offset: The page offset
        :param sort: The sort field.
        :param currentUser: User for access filtering.
        """
        cursor_def = {}
        if user is not None:
            cursor_def['creatorId'] = user['_id']
        if data is not None:
            cursor_def['dataSet'] = data
        if image is not None:
            cursor_def['imageId'] = image['_id']

        cursor = self.find(cursor_def, sort=sort)
        for r in self.filterResultsByPermission(
                cursor=cursor, user=currentUser, level=level,
                limit=limit, offset=offset):
            yield r

    def createTale(self, image, data, creator=None, save=True, title=None,
                   description=None, public=None, config=None, authors=None,
                   icon=None, category=None, illustration=None,
                   licenseSPDX=None,
                   status=TaleStatus.READY, publishInfo=None,
                   relatedIdentifiers=None):

        if creator is None:
            creatorId = None
        else:
            creatorId = creator.get('_id', None)

        if title is None:
            title = f"A tale based on {image['name']}"

        if description is None:
            description = f'This Tale, {title}, represents a computational experiment. ' \
                          f'It contains code, data, and metadata relevant to the experiment.'
        # if illustration is None:
            # Get image from SILS

        now = datetime.datetime.utcnow()
        tale = {
            'authors': authors,
            'category': category,
            'config': config or {},
            'copyOfTale': None,
            'creatorId': creatorId,
            'dataSet': data or [],
            'description': description,
            'format': _currentTaleFormat,
            'created': now,
            'icon': icon,
            'iframe': image.get('iframe', False),
            'imageId': ObjectId(image['_id']),
            'imageInfo': {},
            'illustration': illustration,
            'title': title,
            'public': public,
            'publishInfo': publishInfo or [],
            'relatedIdentifiers': relatedIdentifiers or [],
            'updated': now,
            'licenseSPDX': licenseSPDX or WholeTaleLicense.default_spdx(),
            'status': status,
        }
        if public is not None and isinstance(public, bool):
            self.setPublic(tale, public, save=False)
        else:
            public = False

        if creator is not None:
            self.setUserAccess(tale, user=creator, level=AccessType.ADMIN,
                               save=False)
        if tale['dataSet']:
            eventParams = {'tale': tale, 'user': creator}
            event = events.trigger('tale.update_citation', eventParams)
            if len(event.responses):
                tale = event.responses[-1]

        if save:
            tale = self.save(tale)

        return tale

    def _createAuxFolder(self, tale, rootFolderName, creator=None):
        if creator is None:
            creator = self.model('user').load(tale['creatorId'], force=True)

        if tale['public'] is not None and isinstance(tale['public'], bool):
            public = tale['public']
        else:
            public = False

        rootFolder = getOrCreateRootFolder(rootFolderName)
        auxFolder = self.model('folder').createFolder(
            rootFolder, str(tale['_id']), parentType='folder',
            public=public, reuseExisting=True)
        self.model('folder').setUserAccess(
            auxFolder, user=creator, level=AccessType.ADMIN,
            save=True)
        auxFolder = self.model('folder').setMetadata(
            auxFolder, {'taleId': str(tale['_id'])})
        return auxFolder

    def updateTale(self, tale):
        """
        Updates a tale.

        :param tale: The tale document to update.
        :type tale: dict
        :returns: The tale document that was edited.
        """
        tale['updated'] = datetime.datetime.utcnow()
        return self.save(tale)

    def setAccessList(self, doc, access, save=False, user=None, force=False,
                      setPublic=None, publicFlags=None):
        """
        Overrides AccessControlledModel.setAccessList to encapsulate ACL
        functionality for a tale.

        :param doc: the tale to set access settings on
        :type doc: girder.models.tale
        :param access: The access control list
        :type access: dict
        :param save: Whether the changes should be saved to the database
        :type save: bool
        :param user: The current user
        :param force: Set this to True to set the flags regardless of the passed in
            user's permissions.
        :type force: bool
        :param setPublic: Pass this if you wish to set the public flag on the
            resources being updated.
        :type setPublic: bool or None
        :param publicFlags: Pass this if you wish to set the public flag list on
            resources being updated.
        :type publicFlags: flag identifier str, or list/set/tuple of them,
            or None
        """
        if setPublic is not None:
            self.setPublic(doc, setPublic, save=False)

        if publicFlags is not None:
            doc = self.setPublicFlags(doc, publicFlags, user=user, save=False,
                                      force=force)

        doc = super().setAccessList(
            doc, access, user=user, save=save, force=force)

        for folder in Folder().find({"meta.taleId": str(doc["_id"])}):
            Folder().setAccessList(
                folder, access, user=user, save=save, force=force, recurse=True,
                setPublic=setPublic, publicFlags=publicFlags)

        return doc

    def buildImage(self, tale, user, force=False):
        """
        Build the image for the tale
        """

        resource = {
            'type': 'wt_build_image',
            'tale_id': tale['_id'],
            'tale_title': tale['title']
        }

        token = Token().createToken(user=user, days=0.5)

        notification = init_progress(
            resource, user, 'Building image',
            'Initializing', BUILD_TALE_IMAGE_STEP_TOTAL)

        buildTask = build_tale_image.signature(
            args=[str(tale['_id']), force],
            girder_job_other_fields={
                'wt_notification_id': str(notification['_id']),
            },
            girder_client_token=str(token['_id']),
        ).apply_async()

        return buildTask.job

    @staticmethod
    def _extractZipPayload(stream):
        # TODO: Move assetstore type to wholetale.
        assetstore = next((_ for _ in Assetstore().list() if _['type'] == 101), None)
        if assetstore:
            adapter = assetstore_utilities.getAssetstoreAdapter(assetstore)
            tempDir = adapter.tempDir
        else:
            tempDir = None

        with tempfile.NamedTemporaryFile(dir=tempDir) as fp:
            for chunk in stream(2 * 1024 ** 3):
                fp.write(chunk)
            fp.seek(0)
            if not zipfile.is_zipfile(fp):
                raise GirderException("Provided file is not a zipfile")

            with zipfile.ZipFile(fp) as z:
                manifest_file = next(
                    (_ for _ in z.namelist() if _.endswith('manifest.json')),
                    None
                )
                if not manifest_file:
                    raise GirderException("Provided file doesn't contain a Tale manifest")

                try:
                    manifest = json.loads(z.read(manifest_file).decode())
                    # TODO: is there a better check?
                    manifest['@id'].startswith('https://data.wholetale.org')
                except Exception as e:
                    raise GirderException(
                        "Couldn't read manifest.json or not a Tale: {}".format(str(e))
                    )

                env_file = next(
                    (_ for _ in z.namelist() if _.endswith("environment.json")),
                    None
                )
                try:
                    environment = json.loads(z.read(env_file).decode())
                except Exception as e:
                    raise GirderException(
                        "Couldn't read environment.json or not a Tale: {}".format(str(e))
                    )

                # Extract files to tmp on workspace assetstore
                temp_dir = tempfile.mkdtemp(dir=tempDir)
                # In theory malicious content like: abs path for a member, or relative path with
                # ../.. etc., is taken care of by zipfile.extractall, but in the end we're still
                # unzipping an untrusted content. What could possibly go wrong...?
                z.extractall(path=temp_dir)
        return temp_dir, manifest_file, manifest, environment

    def createTaleFromStream(
        self, stream, user=None, publishInfo=None, relatedIdentifiers=None
    ):
        temp_dir, manifest_file, manifest, environment = self._extractZipPayload(
            stream
        )

        new_tale = ManifestParser.get_tale_fields_from_environment(environment)
        image = imageModel().load(new_tale.pop("imageId"), user=user, level=AccessType.READ)
        new_tale.update(ManifestParser.get_tale_fields_from_manifest(manifest))

        if relatedIdentifiers is None:
            relatedIdentifiers = []

        all_related_ids = relatedIdentifiers + new_tale["relatedIdentifiers"]
        all_related_ids = [
            json.loads(rel_id)
            for rel_id in {json.dumps(_, sort_keys=True) for _ in all_related_ids}
        ]
        new_tale["relatedIdentifiers"] = all_related_ids

        new_tale.update(
            dict(
                creator=user,
                save=True,
                public=False,
                status=TaleStatus.PREPARING,
                publishInfo=publishInfo,
            )
        )

        # We don't call ManifestParser.get_dataset_from_manifest now, cause it might require
        # a registration step. It's going to be called inside import_tale job.

        tale = self.createTale(
            image,
            [],
            **new_tale
        )

        job = Job().createLocalJob(
            title='Import Tale from zip', user=user,
            type='wholetale.import_tale', public=False, _async=True,
            module='girder.plugins.wholetale.tasks.import_tale',
            args=(temp_dir, manifest_file),
            kwargs={'taleId': tale["_id"]}
        )
        Job().scheduleJob(job)
        return tale

    def addGitRepo(self, tale, url, user=None, spawn=False, change_status=False, title=None):
        resource = {
            "type": "wt_git_import",
            "tale_id": tale["_id"],
            "tale_title": tale["title"]
        }
        notification = init_progress(
            resource, user, "Importing from Git", "Initializing", 1
        )

        job = Job().createLocalJob(
            title="Import a git repository as a Tale",
            user=user,
            type="wholetale.import_git_repo",
            public=False,
            _async=True,
            module="girder.plugins.wholetale.tasks.import_git_repo",
            args=(url,),
            kwargs={
                "taleId": tale["_id"],
                "spawn": spawn,
                "change_status": change_status
            },
            otherFields={
                "taleId": tale["_id"],
                "wt_notification_id": str(notification["_id"])
            },
        )
        Job().scheduleJob(job)
        return tale
