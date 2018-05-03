import uuid

from girder import logger
from girder.models.model_base import ValidationException

from .dataone_package import create_minimum_eml
from .dataone_package import generate_system_metadata
from .dataone_package import create_resource_map
from .dataone_utils import check_pid
from .dataone_utils import filter_input_items

from d1_client.mnclient_2_0 import MemberNodeClient_2_0
from d1_common.types.exceptions import DataONEException


def create_client(repoName, auth_token):
    """
    Creates and returns a member node client

    :param repoName: The url of the member node repository
    :param auth_token: The auth token for the user that is using the client
    Should be of the form {"headers": { "Authorization": "Bearer <TOKEN>}}
    :type repoName: str
    :type auth_token: dict
    :return: A client for communicating with a DataONE node
    :rtype: MemberNodeClient_2_0
    """

    return MemberNodeClient_2_0(repoName, **auth_token)


def upload_file(client, pid, object, system_metadata):
    """
    Uploads two files to a DataONE member node. The first is an object, which is just a data file.
    The second is a metadata file describing the file object.

    :param client: A client for communicating with a member node
    :param pid: The pid of the data object
    :param object: The file object that will be uploaded to the member node
    :param system_metadata: The metadata object describing the file object
    :type client: MemberNodeClient_2_0
    :type pid: str
    :type object: str
    :type system_metadata: d1_common.types.generated.dataoneTypes_v2_0.SystemMetadata
    """

    logger.debug('Entered upload_file')
    pid = check_pid(pid)
    try:
        client.create(pid, object, system_metadata)
        logger.debug('Uploaded file')

    except Exception as e:
        raise ValidationException('Error uploading file to DataONE {0}'.format(str(e)))


def create_upload_eml(tale, client, user):
    """
    Creates the EML document along with its metadata document. Once created, they are
    then uploaded to DataONE.

    :param tale: The tale that is being uploaded
    :param client: The client to DataONE
    :param user: The user that is requesting this action
    :type tale: wholetale.models.tale
    :type client: MemberNodeClient_2_0
    :type user: girder.models.user
    :return: pid of the EML document
    :rtype: str
    """

    logger.debug('Entered create_upload_eml')
    # Create the EML metadata
    eml_doc = create_minimum_eml(tale, user)
    eml_pid = str(uuid.uuid4())

    # Create the metadata describing the EML document
    meta = generate_system_metadata(pid=eml_pid,
                                    format_id='eml://ecoinformatics.org/eml-2.1.1',
                                    file_object=eml_doc)

    # meta is type d1_common.types.generated.dataoneTypes_v2_0.SystemMetadata
    # Upload the EML document with its metadata
    # upload_file(client=client, pid=eml_pid, document=eml_doc, system_metadata=meta)
    logger.debug('Leaving create_upload_eml')
    return eml_pid


def create_upload_resmap(res_pid, metadata_pid, obj_pids, client):
    """
    Create the resource map, create its metadata, and then upload them to DataONE

    :param res_pid: The pid for the resource map
    :param metadata_pid: The pid for the metadata document
    :param obj_pids: A list of the pids for each object that was uploaded to DataONE;
     A list of pids that the resource map is documenting.
    :param client: The client to the DataONE member node
    :type res_pid: str
    :type metadata_pid: str
    :type obj_pids: list
    :type client: MemberNodeClient_2_0
    :return: None
    """

    logger.debug('Entered create_upload_resmap')
    logger.debug('Resource Map PID {0}'.format(res_pid))

    res_map = create_resource_map(res_pid, metadata_pid, obj_pids)

    meta = generate_system_metadata(res_pid,
                                    format_id='http://www.openarchives.org/ore/terms',
                                    file_object=res_map)

    # logger.debug('Uploading resource map')
    # upload_file(client=client, pid=res_pid, document=res_map, system_metadata=meta)

    logger.debug('Leaving create_upload_resmap')


def create_upload_object_metadata(client, file_object):
    """
    Creates metadata for a file on the local filesystem and uploads it with the object to DataONE.

    :param client: The client to the DataONE member node
    :param file_object: The file object that will be uploaded
    :type client: MemberNodeClient_2_0
    :type file_object: girder.models.file
    :return: The pid of the object
    :rtype: str
    """

    logger.debug('Entered create_upload_object_metadata')
    pid = str(uuid.uuid4())
    file_path = file_object.get('path', None)

    if file_path is not None:
        meta = generate_system_metadata(pid,
                                        format_id='http://www.openarchives.org/ore/terms',
                                        file_object=file_object,
                                        is_file=True)
    # upload_file(client=client, pid=pid, document=file_object, system_metadata=meta)
    logger.debug('Leaving create_upload_object_metadata')
    return pid


def create_upload_package(item_ids, tale, user, repository='https://dev.nceas.ucsb.edu/knb/d1/mn/'):
    """
    Called when the createPackage endpoint is hit. It takes a list of item ids, a tale id, and the user.

    :param item_ids: A list of items that contain the files that will be uploaded to DataONE
    :param tale: The tale that is being packaged
    :param user: The user that is requesting the upload
    :param repository: The DataONE member node
    :type item_ids: list
    :type tale: girder.models.tale
    :type user: girder.models.user
    :type repository: str
    :return: None
    """

    logger.debug('Entered create_upload_package')
    filtered_items = filter_input_items(item_ids, user)
    dataone_objects = filtered_items['dataone']
    local_objects = filtered_items['local']
    local_file_pids = list()

    try:
        client = create_client(repository, {"headers": {
            "Authorization": "Bearer <TOKEN>"}})

        # for object in dataone_urls:
        #    dataone_pids.append(create_upload_object_metadata(client, object))

        for file in local_objects:
            local_file_pids.append(create_upload_object_metadata(client, file))

        eml_pid = create_upload_eml(tale, client, user)
        create_upload_resmap(str(uuid.uuid4()), eml_pid, dataone_objects+local_file_pids, client)
    except DataONEException as e:
        logger.debug('DataONE Error: {0}'.format(e))

    logger.debug('Leaving create_package')
