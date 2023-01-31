from __future__ import annotations, print_function, unicode_literals

import base64
import json
import os
import tempfile
from concurrent.futures import ThreadPoolExecutor

import boto3
from docarray import Document, DocumentArray


def maybe_download_from_s3(
    docs: DocumentArray, tmpdir: tempfile.TemporaryDirectory, user_input, max_workers
):
    """Downloads file to local temporary dictionary, saves S3 URI to `tags['uri']` and modifies `uri` attribute of
    document to local path in-place.

    :param doc: document containing URI pointing to the location on S3 bucket
    :param tmpdir: temporary directory in which files will be saved
    :param user_input: User iput which contain aws credentials
    :param max_workers: number of threads to create in the threadpool executor to make execution faster
    """

    flat_docs = docs['@c']
    filtered_docs = [c for c in flat_docs if c.uri.startswith('s3://')]

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = []
        for c in filtered_docs:
            f = executor.submit(
                convert_fn,
                c,
                tmpdir,
                user_input.aws_access_key_id,
                user_input.aws_secret_access_key,
                user_input.aws_region_name,
            )
            futures.append(f)
        for f in futures:
            f.result()


def convert_fn(
    d: Document, tmpdir, aws_access_key_id, aws_secret_access_key, aws_region_name
) -> Document:
    """Downloads files and tags from S3 bucket and updates the content uri and the tags uri to the local path"""

    bucket = get_bucket(
        uri=d.uri,
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
        region_name=aws_region_name,
    )
    d.tags['uri'] = d.uri

    d.uri = download_from_bucket(tmpdir, d.uri, bucket)
    if d.uri.endswith('.json'):
        d.load_uri_to_text()
        json_dict = json.loads(d.text)
        field_name = d._metadata['field_name']
        field_value = get_dict_value_for_flattened_key(
            json_dict, field_name.split('__')
        )
        d.text = field_value
        d.uri = ''
    return d


def get_bucket(uri, aws_access_key_id, aws_secret_access_key, region_name):
    session = boto3.session.Session(
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
        region_name=region_name,
    )
    bucket = session.resource('s3').Bucket(uri.split('/')[2])
    return bucket


def download_from_bucket(tmpdir, uri, bucket):
    path_s3 = '/'.join(uri.split('/')[3:])
    path_local = get_local_path(tmpdir, path_s3)
    bucket.download_file(
        path_s3,
        path_local,
    )
    return path_local


def get_dict_value_for_flattened_key(d, keys):
    if len(keys) == 0:
        return d
    else:
        return get_dict_value_for_flattened_key(d[keys[0]], keys[1:])


def get_local_path(tmpdir, path_s3):
    # todo check if this method of creatign the path is creating too much overhead
    # also, the number of files is growing and will never be cleaned up
    return os.path.join(
        str(tmpdir),
        base64.b64encode(bytes(path_s3, "utf-8")).decode("utf-8")
        + f'.{path_s3.split(".")[-1] if "." in path_s3 else ""}',  # preserve file ending
    )
