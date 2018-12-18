#!/usr/bin/env python
# -*- coding: utf-8 -*-

from .resolvers import Resolvers, DOIResolver
from .import_providers import ImportProviders
from .http_provider import HTTPImportProvider
from .null_provider import NullImportProvider
from .dataone.provider import DataOneImportProvider
from .dataverse.provider import DataverseImportProvider
from .globus.globus_provider import GlobusImportProvider


RESOLVERS = Resolvers()
RESOLVERS.add(DOIResolver())

IMPORT_PROVIDERS = ImportProviders()
IMPORT_PROVIDERS.addProvider(DataverseImportProvider())
IMPORT_PROVIDERS.addProvider(GlobusImportProvider())
IMPORT_PROVIDERS.addProvider(DataOneImportProvider())
# (almost) last resort
IMPORT_PROVIDERS.addProvider(HTTPImportProvider())
# just throws exceptions
IMPORT_PROVIDERS.addProvider(NullImportProvider())
