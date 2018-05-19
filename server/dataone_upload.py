import uuid

from girder import logger
from girder.models.model_base import ValidationException
from girder.models.file import File

from .dataone_package import create_minimum_eml
from .dataone_package import generate_system_metadata
from .dataone_package import create_resource_map
from .utils import check_pid
from .utils import filter_items
from .utils import get_tale_artifacts
from .utils import get_file_item

from d1_client.mnclient_2_0 import MemberNodeClient_2_0
from d1_common.types.exceptions import DataONEException


def create_client(repoName, auth_token):
    """
    Creates and returns a member node client

    :param repoName: The url of the member node endpoint
    :param auth_token: The auth token for the user that is using the client
    Should be of the form {"headers": { "Authorization": "Bearer <TOKEN>}}
    :type repoName: str
    :type auth_token: dict
    :return: A client for communicating with a DataONE node
    :rtype: MemberNodeClient_2_0
    """
    return MemberNodeClient_2_0(repoName, **auth_token)


def upload_file(client, pid, file_object, system_metadata):
    """
    Uploads two files to a DataONE member node. The first is an object, which is just a data file.
    The second is a metadata file describing the file object.

    :param client: A client for communicating with a member node
    :param pid: The pid of the data object
    :param file_object: The file object that will be uploaded to the member node
    :param system_metadata: The metadata object describing the file object
    :type client: MemberNodeClient_2_0
    :type pid: str
    :type file_object: str
    :type system_metadata: d1_common.types.generated.dataoneTypes_v2_0.SystemMetadata
    """

    logger.debug('Entered upload_file')
    pid = check_pid(pid)
    try:
        client.create(pid, file_object, system_metadata)
        logger.debug('Uploaded file')

    except Exception as e:
        raise ValidationException('Error uploading file to DataONE. {0}'.format(str(e)))


def create_upload_eml(tale, client, user, item_ids):
    """
    Creates the EML metadata document along with an additional metadata document
    and uploads them both to DataONE. A pid is created for the EML document, and is
    returned so that the resource map can reference it at a later time.

    :param tale: The tale that is being described
    :param client: The client to DataONE
    :param user: The user that is requesting this action
    :param item_ids: The ids of the items that have been uploaded to DataONE
    :type tale: wholetale.models.tale
    :type client: MemberNodeClient_2_0
    :type user: girder.models.user
    :type item_ids: list
    :return: pid of the EML document
    :rtype: str
    """

    logger.debug('Entered create_upload_eml')
    # Create the EML metadata
    eml_pid = str(uuid.uuid4())
    eml_doc = create_minimum_eml(tale, user, item_ids, eml_pid)

    # Create the metadata describing the EML document
    meta = generate_system_metadata(pid=eml_pid,
                                    format_id='eml://ecoinformatics.org/eml-2.1.1',
                                    file_object=eml_doc,
                                    name='science_metadata.xml')

    # meta is type d1_common.types.generated.dataoneTypes_v2_0.SystemMetadata
    # Upload the EML document with its metadata
    upload_file(client=client, pid=eml_pid, file_object=eml_doc, system_metadata=meta)
    logger.debug('Leaving create_upload_eml')
    return eml_pid


def create_upload_resmap(res_pid, eml_pid, obj_pids, client):
    """
    Creates a resource map describing a package and uploads it to DataONE. The
    resource map can be thought of as the glue that holds a package together.

    In order to do this, the following steps are taken.
        1. Create the resource map
        2. Create the metadata document describing the resource map
        3. Upload the pair to DataONE

    :param res_pid: The pid for the resource map
    :param eml_pid: The pid for the metadata document
    :param obj_pids: A list of the pids for each object that was uploaded to DataONE;
     A list of pids that the resource map is documenting.
    :param client: The client to the DataONE member node
    :type res_pid: str
    :type eml_pid: str
    :type obj_pids: list
    :type client: MemberNodeClient_2_0
    :return: None
    """

    logger.debug('Entered create_upload_resmap')
    res_map = create_resource_map(res_pid, eml_pid, obj_pids)
    # To view the contents of res_map, call d1_common.xml.serialize_to_transport()
    meta = generate_system_metadata(res_pid,
                                    format_id='http://www.openarchives.org/ore/terms',
                                    file_object=res_map,
                                    name=str())

    upload_file(client=client, pid=res_pid, file_object=res_map, system_metadata=meta)
    logger.debug('Leaving create_upload_resmap')


def create_upload_object_metadata(client, file_object):
    """
    Takes a file from girder and
        1. Creates metadata describing it
        2. Uploads the file_object with the metadata to DataONE
        3. Returns a pid that is assigned to file_object so that it can
            be added to the resource map later.

    :param client: The client to the DataONE member node
    :param file_object: The file object that will be uploaded
    :type client: MemberNodeClient_2_0
    :type file_object: girder.models.file
    :return: The pid of the object
    :rtype: str
    """

    logger.debug('Entered create_upload_object_metadata')
    pid = str(uuid.uuid4())
    logger.debug(file_object)
    assetstore = File().getAssetstoreAdapter(file_object)

    meta = generate_system_metadata(pid,
                                    format_id=file_object['mimeType'],
                                    file_object=file_object,
                                    name=file_object['name'],
                                    is_file=True)

    upload_file(client=client,
                pid=pid,
                file_object=assetstore.open(file_object).read(),
                system_metadata=meta)

    logger.debug('Leaving create_upload_object_metadata')
    return pid


def get_tale_files(tale, user):
    """
    Gets the tale artifacts and creates a list of files.

    :param tale: The tale whose artifacts are being extracted
    :param user: The user that is requesting the artifacts
    :type tale: wholetale.models.Tale
    :type user: girder.models.User
    :return: A list of the files
    :rtype list
    """
    artifact_items = get_tale_artifacts(tale, user)
    files = list()
    for item in artifact_items:
        files.append(get_file_item(item['_id'], user))
    return files


def create_upload_package(item_ids, tale, user, repository):
    """
    Uploads local or remote files to a DataONE repository.

     There are four cases that need to be handled.
        1. The file  was uploaded directly to Whole Tale and physically exists in Girder.
           In this case, a metadata document needs to be generated for each local file. This
           involves hashing the file, and extracting information about it such as the name,
           description, etc. The file and associated metadata record are uploaded to DataONE
           as a pair.

        2. The file was registered from DataONE, and the file record in Whole Tale points to
           its location in DataONE. Since the file is in DataONE, the file can be referenced in
           the resource map, which avoids uploading redundant data. In this case, the only files
           that are created and uploaded are
              1. A pair of an EML record with its metadata
              2. A resource map describing the package contents

        3. The file was registered from an external source, such as Globus. More generally,
           this is the case where the file record has a link to a file on an external resource
           other than DataONE. To handle this, the file needs to be brought onto the Whole Tale
           filesystem. Once on the local system, metadata is generated for the file and the pair
           are uploaded to DataONE. Once uploaded, the file is removed from

        4. A combination of 1, 2, or 3.

    To handle the different cases, the item_ids are, depending on which case they fall under,
     separated into different containers. Each container is then looped over, and the files
     are dealt with.

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
    filtered_items = filter_items(item_ids, user)
    dataone_object_pids = filtered_items['dataone']
    local_objects = filtered_items['local']
    # globus_objects = filtered_items['globus']
    local_file_pids = list()

    try:
        client = create_client(repository, {"headers": {
            "Authorization": "Bearer eyJhbGciOiJSUzI1NiJ9.eyJzdWIiOiJodHRwOlwvXC9vcmNpZC5vcmdcLzAwMDAtMDAwMi0xNzU2LTIxMjgiLCJmdWxsTmFtZSI6IlRob21hcyBUaGVsZW4iLCJpc3N1ZWRBdCI6IjIwMTgtMDUtMTlUMTc6MTM6MTguMzgzKzAwOjAwIiwiY29uc3VtZXJLZXkiOiJ0aGVjb25zdW1lcmtleSIsImV4cCI6MTUyNjgxNDc5OCwidXNlcklkIjoiaHR0cDpcL1wvb3JjaWQub3JnXC8wMDAwLTAwMDItMTc1Ni0yMTI4IiwidHRsIjo2NDgwMCwiaWF0IjoxNTI2NzQ5OTk4fQ.g5lWjRqG71V0jaeOR8_v3KRWwkITQuVLt76_DYt6RvR9xVkLLdOcsB654SmbFZykrF7Hr4OityDXsu1U-eTRUvTTwsSlG3KyO1llmudcowFQ_CiYsTF0RJxIywwLhPbcXBWy8tjTgxA0Ni7rVNP4v_N8y9UQ1C0BvNVFp9RktLYik0u2tGYrdiotLIsVlNhvUwwjvrdHJ3QHlQIoi34TttIyss4O04iwVN9_wasS3YDrBQRWKkH3hJRcWQXHjcmd1-LUo7ek-cIL_ckcnmg4yV7Ods6FOrfK1Pz56IS-MWYAs1sJq5vWB2OxW1YGNryUwE5D7tf_bLdzO65BL-ZYfEvMUSnggliN6AxpX2dfGGEtBXAvcggX70jm0gR11zK46-bSQLf8ZLin0ZhtZTiPZ8X86NpJVZqmUUpEGU0dQGr5eSq9CrobdVbvyEPd4srwdiqfwVrafjJc-JevE0314VFhQjeko26UezPofUcXUmVT9x6Ydp-RiNdiAPImj3tnZTmPdZ-F8QFSoXj35PjCZbRUFk4SbFsl5OMHNfOo4pVNqSxJR14BW5OEA8UOVzYpdjes0-LsazkQmSsuCYj1F7Bn3lylxE9UqK4Jy1aNRFBs_DMrli2SCiqGf1iyfcme1R1hdSu0T8YZTkz4X6tcsN2fgepsJk6_rwGxg3kwu_o"}})

        for file in local_objects:
            local_file_pids.append(create_upload_object_metadata(client, file))

        eml_pid = create_upload_eml(tale, client, user, item_ids)

        # Combine the lists of pids into a single list that will be used in the resource map
        upload_objects = dataone_object_pids+local_file_pids
        create_upload_resmap(str(uuid.uuid4()), eml_pid, upload_objects, client)

    except DataONEException as e:
        logger.debug('DataONE Error: {}'.format(e))
        raise ValidationException('Error uploading file to DataONE. {0}'.format(str(e)))
    logger.debug('Leaving create_package')
