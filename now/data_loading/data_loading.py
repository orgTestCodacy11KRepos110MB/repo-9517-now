import base64
import json
import os
import pathlib
import pickle
from os.path import join as osp
from typing import List

from docarray import Document, DocumentArray

from now.constants import (
    BASE_STORAGE_URL,
    DEMO_DATASET_DOCARRAY_VERSION,
    DatasetTypes,
    Modalities,
)
from now.data_loading.elasticsearch import ElasticsearchExtractor
from now.demo_data import DemoDatasetNames
from now.log import yaspin_extended
from now.now_dataclasses import UserInput
from now.utils import download, sigmap


def load_data(user_input: UserInput, data_class) -> DocumentArray:
    """Based on the user input, this function will pull the configured DocumentArray dataset ready for the preprocessing
    executor.

    :param user_input: The configured user object. Result from the Jina Now cli dialog.
    :param data_class: The dataclass that should be used for the DocumentArray.
    :return: The loaded DocumentArray.
    """
    da = None
    if user_input.dataset_type == DatasetTypes.DOCARRAY:
        print('⬇  Pull DocumentArray dataset')
        da = _pull_docarray(user_input.dataset_name)
    elif user_input.dataset_type == DatasetTypes.PATH:
        print('💿  Loading files from disk')
        da = _load_from_disk(user_input=user_input, dataclass=data_class)
    elif user_input.dataset_type == DatasetTypes.S3_BUCKET:
        da = _list_files_from_s3_bucket(user_input=user_input, data_class=data_class)
    elif user_input.dataset_type == DatasetTypes.ELASTICSEARCH:
        da = _extract_es_data(user_input)
    elif user_input.dataset_type == DatasetTypes.DEMO:
        print('⬇  Download DocumentArray dataset')
        url = get_dataset_url(user_input.dataset_name, user_input.output_modality)
        da = fetch_da_from_url(url)
    if da is None:
        raise ValueError(
            f'Could not load DocumentArray dataset. Please check your configuration: {user_input}.'
        )
    if 'NOW_CI_RUN' in os.environ:
        da = da[:50]
    if (
        user_input.dataset_name == DemoDatasetNames.MUSIC_GENRES_MIX
        or user_input.dataset_name == DemoDatasetNames.MUSIC_GENRES_ROCK
    ):
        for doc in da:
            if 'genre_tags' in doc.tags and isinstance(doc.tags['genre_tags'], list):
                doc.tags['genre_tags'] = ' '.join(doc.tags['genre_tags'])
    return da


def _pull_docarray(dataset_name: str):
    try:
        return DocumentArray.pull(name=dataset_name, show_progress=True)
    except Exception:
        print(
            '💔 oh no, the secret of your docarray is wrong, or it was deleted after 14 days'
        )
        exit(1)


def _extract_es_data(user_input: UserInput) -> DocumentArray:
    query = {
        'query': {'match_all': {}},
        '_source': True,
    }
    es_extractor = ElasticsearchExtractor(
        query=query,
        index=user_input.es_index_name,
        connection_str=user_input.es_host_name,
    )
    extracted_docs = es_extractor.extract(search_fields=user_input.search_fields)
    return extracted_docs


def _load_from_disk(user_input: UserInput, dataclass) -> DocumentArray:
    dataset_path = user_input.dataset_path.strip()
    dataset_path = os.path.expanduser(dataset_path)
    if os.path.isfile(dataset_path):
        try:
            return DocumentArray.load_binary(dataset_path)
        except Exception:
            print(f'Failed to load the binary file provided under path {dataset_path}')
            exit(1)
    elif os.path.isdir(dataset_path):
        with yaspin_extended(
            sigmap=sigmap, text="Loading data from folder", color="green"
        ) as spinner:
            spinner.ok('🏭')
            docs = from_files(
                dataset_path,
                user_input.search_fields + user_input.filter_fields,
                dataclass,
            )
            return docs
    else:
        raise ValueError(
            f'The provided dataset path {dataset_path} does not'
            f' appear to be a valid file or folder on your system.'
        )


def from_files(
    path: str,
    fields: List[str],
    data_class,
) -> DocumentArray:
    """Creates a Multi Modal documentarray over a list of file path or the content of the files.

    :param path: The path to the directory
    :param fields: The fields to search for in the directory
    :param data_class: The dataclass to use for the document
    """

    def get_subdirectories_local_path(directory):
        return [
            name
            for name in os.listdir(directory)
            if os.path.isdir(os.path.join(directory, name))
        ]

    subdirectories = get_subdirectories_local_path(path)
    if subdirectories:
        docs = create_docs_from_subdirectories(subdirectories, path, fields, data_class)
    else:
        docs = create_docs_from_files(path, fields, data_class)
    return DocumentArray(docs)


def create_docs_from_subdirectories(
    subdirectories: List, path: str, fields: List[str], data_class
) -> List[Document]:
    docs = []
    kwargs = {}
    for subdirectory in subdirectories:
        for file in os.listdir(os.path.join(path, subdirectory)):
            if file in fields:
                kwargs[file.replace('.', '_')] = os.path.join(path, subdirectory, file)
                continue
            if file.endswith('.json'):
                json_f = open(os.path.join(path, subdirectory, file))
                data = json.load(json_f)
                for el, value in data.items():
                    kwargs[el] = value
        docs.append(Document(data_class(**kwargs)))
    return docs


def create_docs_from_files(path: str, fields: List[str], data_class) -> List[Document]:
    docs = []
    for file in os.listdir(os.path.join(path)):
        kwargs = {}
        file_extension = file.split('.')[-1]
        if (
            file_extension == fields[0].split('.')[-1]
        ):  # fields should have only one search field in case of files only
            kwargs[fields[0].replace('.', '_')] = os.path.join(path, file)
            docs.append(Document(data_class(**kwargs)))
    return docs


def _list_files_from_s3_bucket(user_input: UserInput, data_class) -> DocumentArray:
    bucket, folder_prefix = get_s3_bucket_and_folder_prefix(user_input)

    def get_subdirectories(s3_bucket, root_folder):
        sub_directories = []
        for obj in list(s3_bucket.objects.filter(Prefix=root_folder))[1:]:
            if obj.key.endswith('/'):
                sub_directories.append(obj.key)
        return sub_directories

    with yaspin_extended(
        sigmap=sigmap, text="Listing files from S3 bucket ...", color="green"
    ) as spinner:
        spinner.ok('🏭')
        subdirectories = get_subdirectories(bucket, folder_prefix)
        if subdirectories:
            docs = create_docs_from_subdirectories_s3(
                subdirectories,
                folder_prefix,
                user_input.search_fields + user_input.filter_fields,
                data_class,
                bucket,
            )
        else:
            docs = create_docs_from_files_s3(
                folder_prefix,
                user_input.dataset_path,
                user_input.search_fields + user_input.filter_fields,
                data_class,
                bucket,
            )
    return DocumentArray(docs)


def create_docs_from_subdirectories_s3(
    subdirectories: List, path: str, fields: List[str], data_class, bucket
) -> List[Document]:
    docs = []
    kwargs = {}
    for subdirectory in subdirectories:
        for obj in list(bucket.objects.filter(Prefix=subdirectory))[1:]:
            file = obj.key.split('/')[-1]
            file_replaced = file.replace('.', '_')
            file_full_path = '/'.join(path.split('/')[:3]) + '/' + obj.key
            if file in fields:
                kwargs[file_replaced] = file_full_path
                continue
            if file.endswith('.json'):
                kwargs['json_s3'] = file_full_path
        docs.append(Document(data_class(**kwargs)))
    return docs


def create_docs_from_files_s3(
    folder: str, path: str, fields: List[str], data_class, bucket
) -> List[Document]:
    docs = []
    for obj in list(bucket.objects.filter(Prefix=folder))[1:]:
        kwargs = {}
        file = obj.key.split('/')[-1]
        file_replaced = file.replace('.', '_')
        file_full_path = '/'.join(path.split('/')[:3]) + '/' + obj.key
        if file in fields:
            kwargs[file_replaced] = file_full_path
            docs.append(Document(data_class(**kwargs)))
    return docs


def fetch_da_from_url(
    url: str, downloaded_path: str = '~/.cache/jina-now'
) -> DocumentArray:
    data_dir = os.path.expanduser(downloaded_path)
    if not os.path.exists(osp(data_dir, 'data/tmp')):
        os.makedirs(osp(data_dir, 'data/tmp'))
    data_path = (
        data_dir
        + f"/data/tmp/{base64.b64encode(bytes(url, 'utf-8')).decode('utf-8')}.bin"
    )
    if not os.path.exists(data_path):
        download(url, data_path)

    try:
        da = DocumentArray.load_binary(data_path)
    except pickle.UnpicklingError:
        path = pathlib.Path(data_path).expanduser().resolve()
        os.remove(path)
        download(url, data_path)
        da = DocumentArray.load_binary(data_path)
    return da


def get_dataset_url(dataset: str, output_modality: str) -> str:
    data_folder = None
    docarray_version = DEMO_DATASET_DOCARRAY_VERSION
    if output_modality == Modalities.IMAGE:
        data_folder = 'jpeg'
    elif output_modality == Modalities.TEXT:
        data_folder = 'text'
    elif output_modality == Modalities.MUSIC:
        data_folder = 'music'
    elif output_modality == Modalities.VIDEO:
        data_folder = 'video'
    elif output_modality == Modalities.TEXT_AND_IMAGE:
        data_folder = 'text-image'
    if output_modality not in [
        Modalities.MUSIC,
        Modalities.VIDEO,
        Modalities.TEXT_AND_IMAGE,
    ]:
        model_name = 'ViT-B32'
        return f'{BASE_STORAGE_URL}/{data_folder}/{dataset}.{model_name}-{docarray_version}.bin'
    else:
        return f'{BASE_STORAGE_URL}/{data_folder}/{dataset}-{docarray_version}.bin'


def get_s3_bucket_and_folder_prefix(user_input: UserInput):
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
