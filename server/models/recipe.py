# -*- coding: utf-8 -*-

import datetime
import re
import requests

from girder.models.model_base import \
    AccessControlledModel, ValidationException
from girder.constants import AccessType


_GIT_REPO_REGEX = re.compile(r'(\w+://)(.+@)*([\w\d\.]+)(:[\d]+){0,1}/*(.*)')


class Recipe(AccessControlledModel):

    def initialize(self):
        self.name = 'recipe'
        self.ensureIndices(
            ('parentId', 'name', 'commitId', 'url',
             ([('parentId', 1), ('name', 1), ('commitId', 1), ('url', 1)], {}))
        )
        self.ensureTextIndex({
            'name': 10,
            'description': 1
        })
        self.exposeFields(
            level=AccessType.READ,
            fields={'_id', 'commitId', 'created', 'creatorId', 'description',
                    'updated', 'name', 'parentId', 'public', 'tags', 'url'})

    def validate(self, recipe):
        if not _GIT_REPO_REGEX.match(recipe['url']):
            raise ValidationException(
                'Invalid git repository: %s.' % recipe['url'],
                field='url')
        repo = _GIT_REPO_REGEX.match(recipe['url']).groups()[-1].split('/')
        if len(repo) < 2:
            raise ValidationException(
                'URL does not contain repository name: %s.' % recipe['url'],
                field='url')
        try:
            resp = requests.get(
                'https://api.github.com/repos/%s/%s' % (repo[0], repo[1]))
            resp.raise_for_status()
        except requests.HTTPError:
            raise ValidationException(
                'Cannot access %s or it does not exist' % recipe['url'],
                field='url')

        try:
            resp = requests.get(
                'https://api.github.com/repos/%s/%s/commits/%s' %
                (repo[0], repo[1], recipe['commitId']))
            resp.raise_for_status()
        except requests.HTTPError:
            raise ValidationException(
                'Commit Id %s does not exist in repository %s/%s' % (
                    recipe['commitId'], repo[0], repo[1]), field='commitId')

        q = {
            'url': recipe['url'],
            'commitId': recipe['commitId']
        }
        if '_id' in recipe:
            q['_id'] = {'$ne': recipe['_id']}
        if self.findOne(q, fields=['_id']):
            raise ValidationException('A recipe with that url and commitId '
                                      'already exists.', 'commitId')

        if not recipe['name']:
            recipe['name'] = '/'.join(repo[:2])
        recipe['name'] = recipe['name'].strip()
        recipe['lowerName'] = recipe['name'].lower()
        if recipe['description']:
            recipe['description'] = recipe['description'].strip()

        return recipe

    def createRecipe(self, commitId, url, name=None, tags=None, creator=None,
                     save=True, parent=None, description=None, public=None):

        # TODO: check for existing recipe based on URL

        if creator is None:
            creatorId = None
        else:
            creatorId = creator.get('_id', None)

        if parent is not None:
            parentId = parent['_id']
        else:
            parentId = None

        if tags is None:
            tags = ['latest']
        else:
            if 'latest' not in tags:
                tags.append('latest')

        now = datetime.datetime.utcnow()
        recipe = {
            'commitId': commitId,
            'created': now,
            'creatorId': creatorId,
            'description': description,
            'name': name,
            'parentId': parentId,
            'public': public,
            'tags': tags,
            'updated': now,
            'url': url
        }

        if creator is not None:
            self.setUserAccess(recipe, user=creator, level=AccessType.ADMIN,
                               save=False)
        if public is not None and isinstance(public, bool):
            self.setPublic(recipe, public, save=False)

        if save:
            recipe = self.save(recipe)
        return recipe

    def updateRecipe(self, recipe):
        """
        Updates a recipe.

        :param recipe: The recipe document to update.
        :type recipe: dict
        :returns: The recipe document that was edited.
        """
        recipe['updated'] = datetime.datetime.utcnow()
        return self.save(recipe)

    def setAccessList(self, doc, access, save=False, user=None, force=False,
                      setPublic=None, publicFlags=None):
        """
        Overrides AccessControlledModel.setAccessList to encapsulate ACL
        functionality for a recipe.

        :param doc: the recipe to set access settings on
        :type doc: girder.models.recipe
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

        return AccessControlledModel.setAccessList(self, doc, access, user=user,
                                                   save=save, force=force)
