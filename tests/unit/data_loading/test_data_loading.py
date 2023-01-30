""" This suite tests the data_loading.py module """
import os
import pathlib
from typing import Tuple

import pytest
import requests
from docarray import Document, DocumentArray, dataclass
from docarray.typing import Image, Text
from pytest_mock import MockerFixture

from now.app.search_app import SearchApp
from now.constants import DatasetTypes
from now.data_loading.create_dataclass import (
    create_dataclass,
    create_dataclass_fields_file_mappings,
    update_dict_with_no_overwrite,
)
from now.data_loading.data_loading import (
    _list_files_from_s3_bucket,
    from_files_local,
    load_data,
)
from now.demo_data import AVAILABLE_DATASETS, DemoDatasetNames
from now.now_dataclasses import UserInput


@pytest.fixture()
def da() -> DocumentArray:
    cur_dir = pathlib.Path(__file__).parent.resolve()

    @dataclass
    class MMDoc:
        description: Text = 'description'
        image: Image = os.path.join(cur_dir, '../../resources/gif/folder1/file.gif')

    return DocumentArray(
        [Document(MMDoc(description='foo')), Document(MMDoc(description='bar'))]
    )


@pytest.fixture(autouse=True)
def mock_download(mocker: MockerFixture, da: DocumentArray):
    def fake_download(url: str, filename: str) -> str:
        da.save_binary(filename)
        return filename

    mocker.patch('now.utils.download', fake_download)


@pytest.fixture(autouse=True)
def mock_pull(mocker: MockerFixture, da: DocumentArray):
    def fake_pull(secret: str, admin_name: str) -> DocumentArray:
        return da

    mocker.patch('now.data_loading.data_loading._pull_docarray', fake_pull)


@pytest.fixture()
def local_da(da: DocumentArray, tmpdir: str) -> Tuple[str, DocumentArray]:
    save_path = os.path.join(tmpdir, 'da.bin')
    da.save_binary(save_path)
    yield save_path, da
    if os.path.isfile(save_path):
        os.remove(save_path)


def is_da_text_equal(da_a: DocumentArray, da_b: DocumentArray):
    for a, b in zip(da_a, da_b):
        if a.text != b.text:
            return False
    return True


def test_da_local_path(local_da: Tuple[str, DocumentArray]):
    path, da = local_da
    user_input = UserInput()
    user_input.dataset_type = DatasetTypes.PATH
    user_input.dataset_path = path
    user_input.index_fields = ['description']

    loaded_da = load_data(user_input)
    assert loaded_da[0].tags == {}
    assert loaded_da[0].description.content == da[0].description.content
    assert len(loaded_da) == 2
    assert len(loaded_da[0].chunks) == 1


def test_da_local_path_image_folder(image_resource_path: str):
    user_input = UserInput()
    user_input.dataset_type = DatasetTypes.PATH
    user_input.dataset_path = image_resource_path

    user_input.index_fields = ['a.jpg']
    user_input.index_field_candidates_to_modalities = {'a.jpg': Image}
    data_class, user_input.field_names_to_dataclass_fields = create_dataclass(
        user_input=user_input
    )
    loaded_da = load_data(user_input, data_class)

    assert len(loaded_da) == 2, (
        f'Expected two images, got {len(loaded_da)}.'
        f' Check the tests/resources/image folder'
    )
    for doc in loaded_da:
        assert doc.chunks[0].uri
        assert doc.chunks[0].content is not None


def test_da_custom_ds(da: DocumentArray):
    user_input = UserInput()
    user_input.dataset_type = DatasetTypes.DEMO
    user_input.dataset_name = DemoDatasetNames.DEEP_FASHION
    user_input.admin_name = 'team-now'
    user_input.index_fields = ['description']

    loaded_da = load_data(user_input)

    assert len(loaded_da) > 0
    for doc in loaded_da:
        assert doc.tags == {}
        assert doc.chunks


def test_from_files_local(resources_folder_path):
    user_input = UserInput()
    user_input.dataset_type = DatasetTypes.PATH
    user_input.index_fields = ['a.jpg', 'test.txt']
    user_input.index_field_candidates_to_modalities = {
        'a.jpg': Image,
        'test.txt': Text,
    }
    user_input.dataset_path = os.path.join(resources_folder_path, 'subdirectories')
    file_fields_file_mappings = create_dataclass_fields_file_mappings(
        user_input.index_fields, user_input.index_field_candidates_to_modalities
    )

    data_class, user_input.field_names_to_dataclass_fields = create_dataclass(
        user_input=user_input
    )
    loaded_da = from_files_local(
        user_input.dataset_path,
        user_input.index_fields,
        file_fields_file_mappings,
        data_class,
    )

    assert len(loaded_da) == 2
    for doc in loaded_da:
        assert doc.chunks[0].uri


def test_from_subfolders_s3(get_aws_info):
    user_input = UserInput()
    (
        user_input.dataset_path,
        user_input.aws_access_key_id,
        user_input.aws_secret_access_key,
        user_input.aws_region_name,
    ) = get_aws_info
    user_input.dataset_type = DatasetTypes.S3_BUCKET
    user_input.index_fields = ['image.png', 'test.txt']
    user_input.index_field_candidates_to_modalities = {
        'image.png': Image,
        'test.txt': Text,
    }
    user_input.filter_fields = ['tags', 'id', 'title']
    user_input.filter_field_candidates_to_modalities = {
        'tags': str,
        'id': str,
        'title': str,
    }

    all_modalities = {}
    all_modalities.update(user_input.index_field_candidates_to_modalities)
    update_dict_with_no_overwrite(
        all_modalities, user_input.filter_field_candidates_to_modalities
    )
    data_class, user_input.field_names_to_dataclass_fields = create_dataclass(
        user_input=user_input
    )

    loaded_da = _list_files_from_s3_bucket(user_input, data_class)
    assert len(loaded_da) == 2
    for doc in loaded_da:
        assert doc.chunks[0].uri
        assert doc.chunks[1].uri


@pytest.fixture
def user_input():
    user_input = UserInput()
    user_input.dataset_path = ''
    user_input.app_instance = SearchApp()
    return user_input


def get_data(gif_resource_path, files):
    return DocumentArray(
        Document(uri=os.path.join(gif_resource_path, file)) for file in files
    )


@pytest.mark.parametrize(
    'ds_name',
    [
        ds.name
        for _, demo_datasets in AVAILABLE_DATASETS.items()
        for ds in demo_datasets
    ],
)
def test_dataset_is_available(
    ds_name: str,
):
    token = os.environ['WOLF_TOKEN']
    cookies = {'st': token}
    json_data = {'name': ds_name}
    response = requests.post(
        'https://api.hubble.jina.ai/v2/rpc/docarray.getFirstDocuments',
        cookies=cookies,
        json=json_data,
    )
    assert response.json()['code'] == 200
