#!/usr/bin/env python
# -*- coding: utf-8 -*-
from girder.api import access
from girder.api.describe import Description, describeRoute
from girder.api.rest import Resource


class License(Resource):

    def __init__(self):
        super(License, self).__init__()
        self.resourceName = 'license'
        self.route('GET', (), self.get_licenses)

    @access.public
    @describeRoute(
        Description('Return the licenses that a Tale can be under.')
        .notes('This endpoint returns a list of all of the Whole Tale supported licenses')
    )
    def get_licenses(self, params):
        return [
            {
                'name': 'Creative Commons Zero v1.0 Universal',
                'spdx': 'CCO-1.0',
                'text': 'This work is dedicated to the public domain under the Creative Commons '
                        'Universal 1.0 Public Domain Dedication. To view a copy of this '
                        'dedication, visit https://creativecommons.org/publicdomain/zero/1.0/.'
            },
            {
                'name': 'Creative Commons Attribution 4.0 International',
                'spdx': 'CC-BY-4.0',
                'text': 'This work is licensed under the Creative Commons Attribution 4.0 '
                        'International License. To view a copy of this license, '
                        'visit http://creativecommons.org/licenses/by/4.0/.'
            }
        ]
