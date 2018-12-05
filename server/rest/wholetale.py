#!/usr/bin/env python
# -*- coding: utf-8 -*-
from girder.api import access
from girder.api.describe import Description, describeRoute
from girder.api.rest import Resource

from ..constants import API_VERSION


class wholeTale(Resource):

    def __init__(self):
        super(wholeTale, self).__init__()
        self.resourceName = 'wholetale'

        self.route('GET', (), self.get_wholetale_info)

    @access.public
    @describeRoute(
        Description('Return basic info about Whole Tale plugin')
    )
    def get_wholetale_info(self, params):
        return {'api_version': API_VERSION}
