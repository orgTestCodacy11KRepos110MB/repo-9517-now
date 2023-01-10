from __future__ import annotations, print_function, unicode_literals

from docarray.typing import Image, Text, Video

from now.utils import BetterEnum

DOCKER_BFF_PLAYGROUND_TAG = '0.0.146-fix-webcam-not-working-4'
NOW_PREPROCESSOR_VERSION = '0.0.120-fix-pull-docarray-4'
NOW_ELASTIC_INDEXER_VERSION = '0.0.142-fix-pull-docarray-4'
NOW_AUTOCOMPLETE_VERSION = '0.0.8-fix-pull-docarray-4'


class Apps(BetterEnum):
    SEARCH_APP = 'search_app'


class DatasetTypes(BetterEnum):
    DEMO = 'demo'
    PATH = 'path'
    DOCARRAY = 'docarray'
    S3_BUCKET = 's3_bucket'
    ELASTICSEARCH = 'elasticsearch'


SUPPORTED_FILE_TYPES = {
    Text: ['txt', 'md'],
    Image: ['jpg', 'jpeg', 'png', 'bmp', 'tiff', 'tif'],
    Video: ['gif'],
}

FILETYPE_TO_MODALITY = {
    filetype: modality
    for modality, filetypes in SUPPORTED_FILE_TYPES.items()
    for filetype in filetypes
}
AVAILABLE_MODALITIES_FOR_SEARCH = [Text, Image, Video]
AVAILABLE_MODALITIES_FOR_FILTER = [Text]
NOT_AVAILABLE_MODALITIES_FOR_FILTER = [Image, Video]

BASE_STORAGE_URL = (
    'https://storage.googleapis.com/jina-fashion-data/data/one-line/datasets'
)

EXTERNAL_CLIP_HOST = 'encoderclip-pretty-javelin-3aceb7f2cd.wolf.jina.ai'

DEFAULT_FLOW_NAME = 'nowapi'
PREFETCH_NR = 10

SURVEY_LINK = 'https://10sw1tcpld4.typeform.com/to/VTAyYRpR?utm_source=cli'

TAG_OCR_DETECTOR_TEXT_IN_DOC = '_ocr_detector_text_in_doc'
TAG_INDEXER_DOC_HAS_TEXT = '_indexer_doc_has_text'
EXECUTOR_PREFIX = 'jinahub+docker://'
ACCESS_PATHS = '@cc'
