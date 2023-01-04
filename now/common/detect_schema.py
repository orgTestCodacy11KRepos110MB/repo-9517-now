import itertools
import json
import os
from typing import Dict, List

import requests

from now.constants import (
    AVAILABLE_MODALITIES_FOR_FILTER,
    AVAILABLE_MODALITIES_FOR_SEARCH,
    MODALITIES_MAPPING,
    NOT_AVAILABLE_MODALITIES_FOR_FILTER,
    SUPPORTED_FILE_TYPES,
    Modalities,
)
from now.now_dataclasses import UserInput


def _create_candidate_index_filter_fields(field_name_to_value):
    """
    Creates candidate index fields from the field_names for s3
    and local file path.
    A candidate index field is a field that we can detect its modality
    A candidate filter field is a field that we can't detect its modality,
    or it's modality is different from image, video or audio.

    :param field_name_to_value: dictionary
    """
    index_fields_modalities = {}
    filter_field_modalities = {}
    not_available_file_types_for_filter = list(
        itertools.chain(
            *[
                SUPPORTED_FILE_TYPES[modality]
                for modality in NOT_AVAILABLE_MODALITIES_FOR_FILTER
            ]
        )
    )
    for field_name, field_value in field_name_to_value.items():
        # we determine search modality
        for modality in AVAILABLE_MODALITIES_FOR_SEARCH:
            file_types = SUPPORTED_FILE_TYPES[modality]
            if field_name.split('.')[-1] in file_types:
                index_fields_modalities[field_name] = MODALITIES_MAPPING[modality]
                break
            elif field_name == 'uri' and field_value.split('.')[-1] in file_types:
                index_fields_modalities[field_name] = MODALITIES_MAPPING[modality]
                break
        if field_name == 'text' and field_value:
            index_fields_modalities[field_name] = MODALITIES_MAPPING[Modalities.TEXT]

        # we determine if it's a filter field
        if (
            field_name == 'uri'
            and field_value.split('.')[-1] not in not_available_file_types_for_filter
        ) or field_name.split('.')[-1] not in not_available_file_types_for_filter:
            filter_field_modalities[field_name] = field_value.__class__

    if len(index_fields_modalities.keys()) == 0:
        raise ValueError(
            'No searchable fields found, please check documentation https://now.jina.ai'
        )
    return index_fields_modalities, filter_field_modalities


def get_first_file_in_folder_structure_s3(bucket, folder_prefix, dataset_path):
    try:
        # gets the first file in an s3 bucket, index 0 is reserved for the root folder name
        first_file = list(bucket.objects.filter(Prefix=folder_prefix).limit(2))[1].key
        i = 2
        while first_file.split('/')[-1].startswith('.'):
            first_file = list(bucket.objects.filter(Prefix=folder_prefix).limit(i + 1))[
                i
            ].key
            i += 1
    except Exception as e:
        raise Exception(f'Empty folder {dataset_path}, data is missing.')
    return first_file


def _extract_field_candidates_docarray(response):
    """
    Downloads the first document in the document array and extracts field names from it
    if tags also exists then it extracts the keys from tags and adds to the field_names
    """
    search_modalities = {}
    filter_modalities = {}
    doc = requests.get(response.json()['data']['download']).json()[0]
    if (
        not doc.get('_metadata', None)
        or 'multi_modal_schema' not in doc['_metadata']['fields']
    ):
        raise RuntimeError(
            'Multi-modal schema is not provided. Please prepare your data following this guide - '
            'https://docarray.jina.ai/datatypes/multimodal/'
        )
    mm_schema = doc['_metadata']['fields']['multi_modal_schema']
    mm_fields = mm_schema['structValue']['fields']
    for field_name, value in mm_fields.items():
        if 'position' not in value['structValue']['fields']:
            raise ValueError(
                f'No modality found for the dataclass field: `{field_name}`. Please follow the steps in the '
                f'documentation to add modalities to your documents https://docarray.jina.ai/datatypes/multimodal/'
            )
        field_pos = value['structValue']['fields']['position']['numberValue']
        if not doc['chunks'][field_pos]['modality']:
            raise ValueError(
                f'No modality found for {field_name}. Please follow the steps in the documentation'
                f' to add modalities to your documents https://docarray.jina.ai/datatypes/multimodal/'
            )
        modality = doc['chunks'][field_pos]['modality'].lower()
        if modality not in AVAILABLE_MODALITIES_FOR_SEARCH:
            raise ValueError(
                f'The modality {modality} is not supported for search. Please use '
                f'one of the following modalities: {AVAILABLE_MODALITIES_FOR_SEARCH}'
            )
        # only the available modalities for filter are added to the filter modalities
        if modality in AVAILABLE_MODALITIES_FOR_FILTER:
            filter_modalities[field_name] = modality
        # only the available modalities for search are added to search modalities
        if modality in AVAILABLE_MODALITIES_FOR_SEARCH:
            search_modalities[field_name] = MODALITIES_MAPPING[modality]

    if doc.get('tags', None):
        for el, value in doc['tags']['fields'].items():
            for val_type, val in value.items():
                filter_modalities[el] = val_type

    if len(search_modalities.keys()) == 0:
        raise ValueError(
            'No searchable fields found, please check documentation https://now.jina.ai'
        )
    return search_modalities, filter_modalities


def set_field_names_from_docarray(user_input: UserInput, **kwargs):
    """
    Get the schema from a DocArray

    :param user_input: UserInput object

    Makes a request to hubble API and downloads the first 10 documents
    from the document array and uses the first document to get the schema and sets field_names in user_input
    """
    cookies = {
        'st': user_input.jwt['token'],
    }

    json_data = {
        'name': user_input.dataset_name,
    }
    response = requests.post(
        'https://api.hubble.jina.ai/v2/rpc/docarray.getFirstDocuments',
        cookies=cookies,
        json=json_data,
    )
    if response.json()['code'] == 200:
        (
            user_input.index_fields_modalities,
            user_input.filter_fields_modalities,
        ) = _extract_field_candidates_docarray(response)
    else:
        raise ValueError('DocumentArray does not exist or you do not have access to it')


def _extract_field_names_single_folder(
    file_paths: List[str], separator: str
) -> Dict[str, str]:
    """This function extracts the file endings in a single folder and returns them as field names.
    It works with a local file structure or a remote file structure.

    :param file_paths: list of relative file paths from data set path
    :param separator: separator used in the file paths
    :return: list of file endings
    """
    file_endings = set(
        ['.' + path.split(separator)[-1].split('.')[-1] for path in file_paths]
    )
    return {file_ending: file_ending for file_ending in file_endings}


def _extract_field_names_sub_folders(
    file_paths: List[str], separator: str, s3_bucket=None
) -> Dict[str, str]:
    """This function extracts the files in sub folders and returns them as field names. Also, it reads json files
    and adds them as key-value pairs to the field names dictionary.
    It works with a local file structure or a remote file structure.

    :param file_paths: list of relative file paths from data set path
    :param separator: separator used in the file paths
    :param s3_bucket: s3 bucket object, only needed if interacting with s3 bucket
    :return: list of file endings
    """
    field_names = {}
    for path in file_paths:
        if path.endswith('.json'):
            if s3_bucket:
                data = json.loads(s3_bucket.Object(path).get()['Body'].read())
            else:
                with open(path) as f:
                    data = json.load(f)
            for el, value in data.items():
                field_names[el] = value
        else:
            file_name = path.split(separator)[-1]
            field_names[file_name] = file_name
    return field_names


def set_field_names_from_s3_bucket(user_input: UserInput, **kwargs):
    """
    Get the schema from a S3 bucket

    :param user_input: UserInput object

    checks if the bucket exists and the format of the folder structure is correct,
    if yes then downloads the first folder and sets its content as field_names in user_input
    """
    bucket, folder_prefix = get_s3_bucket_and_folder_prefix(user_input)
    # user has to provide the folder where folder structure begins
    first_file = get_first_file_in_folder_structure_s3(
        bucket, folder_prefix, user_input.dataset_path
    )
    structure_identifier = first_file[len(folder_prefix) :].split('/')
    folder_structure = (
        'sub_folders' if len(structure_identifier) > 1 else 'single_folder'
    )
    if folder_structure == 'single_folder':
        objects = list(bucket.objects.filter(Prefix=folder_prefix).limit(100))
        file_paths = [
            obj.key
            for obj in objects
            if not obj.key.endswith('/') and not obj.key.split('/')[-1].startswith('.')
        ]
        field_names = _extract_field_names_single_folder(file_paths, '/')
    elif folder_structure == 'sub_folders':
        first_folder = '/'.join(first_file.split('/')[:-1])
        first_folder_objects = [
            obj.key
            for obj in bucket.objects.filter(Prefix=first_folder)
            if not obj.key.endswith('/') and not obj.key.split('/')[-1].startswith('.')
        ]
        field_names = _extract_field_names_sub_folders(
            first_folder_objects, '/', bucket
        )
    (
        user_input.index_fields_modalities,
        user_input.filter_fields_modalities,
    ) = _create_candidate_index_filter_fields(field_names)


def set_field_names_from_local_folder(user_input: UserInput, **kwargs):
    """
    Get the schema from a local folder

    :param user_input: UserInput object

    checks if the folder exists and the format of the folder structure is correct,
    if yes set the content of the first folder as field_names in user_input
    """
    dataset_path = user_input.dataset_path.strip()
    dataset_path = os.path.expanduser(dataset_path)
    if os.path.isfile(dataset_path):
        raise ValueError(
            'The path provided is not a folder, please check documentation https://now.jina.ai'
        )
    file_paths = []
    folder_generator = os.walk(dataset_path, topdown=True)
    current_level = folder_generator.__next__()
    # check if the first level contains any folders
    folder_structure = 'sub_folders' if len(current_level[1]) > 0 else 'single_folder'
    if folder_structure == 'single_folder':
        file_paths.extend(
            [
                os.path.join(dataset_path, file)
                for file in current_level[2]
                if not file.startswith('.')
            ]
        )
        field_names = _extract_field_names_single_folder(file_paths, os.sep)
    elif folder_structure == 'sub_folders':
        # depth-first search of the first nested folder containing files
        while len(current_level[1]) > 0:
            current_level = folder_generator.__next__()
        first_folder = current_level[0]
        first_folder_files = [
            os.path.join(first_folder, file)
            for file in os.listdir(first_folder)
            if os.path.isfile(os.path.join(first_folder, file))
            and not file.startswith('.')
        ]
        field_names = _extract_field_names_sub_folders(first_folder_files, os.sep)
    (
        user_input.index_fields_modalities,
        user_input.filter_fields_modalities,
    ) = _create_candidate_index_filter_fields(field_names)


def get_s3_bucket_and_folder_prefix(user_input: UserInput):
    """
    Gets the s3 bucket and folder prefix from the user input.

    :param user_input: The user input

    :return: The s3 bucket and folder prefix
    """
    import boto3.session

    s3_uri = user_input.dataset_path
    if not s3_uri.startswith('s3://'):
        raise ValueError(
            f"Can't process S3 URI {s3_uri} as it assumes it starts with: 's3://'"
        )

    bucket = s3_uri.split('/')[2]
    folder_prefix = '/'.join(s3_uri.split('/')[3:])

    session = boto3.session.Session(
        aws_access_key_id=user_input.aws_access_key_id,
        aws_secret_access_key=user_input.aws_secret_access_key,
    )
    bucket = session.resource('s3').Bucket(bucket)

    return bucket, folder_prefix
