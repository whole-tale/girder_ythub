from tests import base
from girder.api.rest import RestException
from girder.constants import ROOT_DIR
from girder.models.model_base import ValidationException

from d1_client.mnclient_2_0 import MemberNodeClient_2_0
from d1_common.types import dataoneTypes
import uuid


def setUpModule():

    base.enabledPlugins.append('wholetale')
    base.startServer()


def tearDownModule():

    base.stopServer()
