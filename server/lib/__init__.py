#!/usr/bin/env python
# -*- coding: utf-8 -*-

from .resolvers import Resolvers, DOIResolver
from .import_providers import ImportProviders
from .http_provider import HTTPImportProvider
from .null_provider import NullImportProvider
from .dataone.dataone_provider import DataOneImportProvider
from .globus.globus_provider import GlobusImportProvider


RESOLVERS = Resolvers()
RESOLVERS.add(DOIResolver())

IMPORT_PROVIDERS = ImportProviders()
IMPORT_PROVIDERS.addProvider(DataOneImportProvider())
IMPORT_PROVIDERS.addProvider(GlobusImportProvider())
# (almost) last resort
IMPORT_PROVIDERS.addProvider(HTTPImportProvider())
# just throws exceptions
IMPORT_PROVIDERS.addProvider(NullImportProvider())
