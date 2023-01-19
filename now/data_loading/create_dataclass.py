import typing
from collections import defaultdict
from typing import Dict, List

from docarray import dataclass, field

from now.constants import AVAILABLE_MODALITIES_FOR_SEARCH, DatasetTypes
from now.now_dataclasses import UserInput
from now.utils import docarray_typing_to_modality_string


def update_dict_with_no_overwrite(dict1: Dict, dict2: Dict):
    """
    Update dict1 with dict2, but only if the key does not exist in dict1

    :param dict1: dict to be updated
    :param dict2: dict to be used for updating
    """
    for key, value in dict2.items():
        if key not in dict1:
            dict1[key] = value


def create_dataclass(
    fields: List = None,
    fields_modalities: Dict = None,
    dataset_type: DatasetTypes = None,
    user_input: UserInput = None,
):
    """
    Create a dataclass from the selected index and filter fields
    and their corresponding modalities or directly from the user input which should
    contain that information. If both are provided, the user input will be used.

    for example:
    the index fields modalities can be:
    {'test.txt': Text , 'image.png': Image}
    the filter fields modalities can be:
    {'price': float, 'description': str}

    the dataclass will be:

    @dataclass
    class DataClass:
        text_0: Text
        image_0: Image
        price: float
        description: str

    :param fields: list of fields
    :param fields_modalities: dict of fields and their modalities
    :param dataset_type: dataset type
    :param user_input: user inputs

    :return: dataclass object
    """

    if user_input:
        fields_modalities = {}
        fields_modalities.update(user_input.index_field_candidates_to_modalities)
        update_dict_with_no_overwrite(
            fields_modalities, user_input.filter_field_candidates_to_modalities
        )
        fields = user_input.index_fields + user_input.filter_fields
        dataset_type = user_input.dataset_type

    file_mapping_to_dataclass_fields = create_dataclass_fields_file_mappings(
        fields,
        fields_modalities,
    )
    field_names_to_dataclass_fields = file_mapping_to_dataclass_fields
    (all_annotations, all_class_attributes,) = create_annotations_and_class_attributes(
        fields,
        fields_modalities,
        file_mapping_to_dataclass_fields,
        dataset_type,
    )

    mm_doc = type("MMDoc", (object,), all_class_attributes)
    setattr(mm_doc, '__annotations__', all_annotations)
    mm_doc = dataclass(mm_doc)

    return mm_doc, field_names_to_dataclass_fields


def create_annotations_and_class_attributes(
    fields: List,
    fields_modalities: Dict,
    field_names_to_dataclass_fields: Dict,
    dataset_type: DatasetTypes = None,
):
    """
    Create annotations and class attributes for the dataclass
    In case of S3 bucket, new field is created to prevent uri loading


    :param fields: list of fields
    :param fields_modalities: dict of fields and their modalities
    :param field_names_to_dataclass_fields: dict of selected field names and their corresponding fields in dataclass
    :param dataset_type: dataset type
    """
    annotations = {}
    class_attributes = {}
    S3Object, my_setter, my_getter = create_s3_type()

    for f in fields:
        if not isinstance(f, typing.Hashable):
            continue
        if dataset_type == DatasetTypes.S3_BUCKET:
            annotations[field_names_to_dataclass_fields[f]] = S3Object
            class_attributes[field_names_to_dataclass_fields[f]] = field(
                setter=my_setter, getter=my_getter, default=''
            )
        else:
            annotations[field_names_to_dataclass_fields[f]] = fields_modalities[f]
            class_attributes[field_names_to_dataclass_fields[f]] = None
    return annotations, class_attributes


def create_s3_type():
    """
    Create a new type for S3 bucket
    """
    from typing import TypeVar

    from docarray import Document

    S3Object = TypeVar('S3Object', bound=str)

    def my_setter(value) -> 'Document':
        """
        Custom setter for the S3Object type that doesn't load the content from the URI
        """
        return Document(uri=value)

    def my_getter(doc: 'Document'):
        return doc.uri

    return S3Object, my_setter, my_getter


def create_dataclass_fields_file_mappings(fields: List, fields_modalities: Dict):
    """
    Create a mapping between the dataclass fields and the file fields

    :param fields: list of fields
    :param fields_modalities: dict of fields and their modalities
    """

    modalities_count = defaultdict(int)

    dataclass_fields_to_file_mapping = {}
    filter_count = 0
    for f in fields:
        if not isinstance(f, typing.Hashable):
            continue
        field_modality = fields_modalities[f]
        if field_modality in AVAILABLE_MODALITIES_FOR_SEARCH:
            dataclass_fields_to_file_mapping[
                f'{docarray_typing_to_modality_string(field_modality)}_{modalities_count[field_modality]}'
            ] = f
            modalities_count[fields_modalities[f]] += 1
        else:
            dataclass_fields_to_file_mapping[f'filter_{filter_count}'] = f
            filter_count += 1
    file_mapping_to_dataclass_fields = {
        v: k for k, v in dataclass_fields_to_file_mapping.items()
    }
    return file_mapping_to_dataclass_fields
