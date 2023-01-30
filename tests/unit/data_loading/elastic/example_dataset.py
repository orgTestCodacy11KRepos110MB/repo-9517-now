import gzip
import json
import pathlib
from typing import Dict, Optional

from tests.unit.data_loading.elastic.utils import create_es_index, es_insert

from now.data_loading.elasticsearch import ElasticsearchConnector


class ExampleDataset:
    def __init__(self, filepath: str):
        """
        Parses and stores all information associated with the given example dataset.
        :param filepath: Path to example dataset
        """
        self._filepath = pathlib.Path(filepath)
        self._corpus = self._parse_corpus_file()

    def import_to_elastic_search(
        self,
        connection_str: str,
        connection_args: Dict,
        index_name: str,
        mapping_path: Optional[str] = None,
        size: int = None,
    ):
        """
        Creates an Elasticsearch index for the documents parsed from the file of the
        example dataset
        :param connection_str: Elasticsearch connection string
        :param connection_args: Additional connection arguments
        :param index_name: Name for Elasticsearch index
        :param mapping_path: Path to json file storing the mapping of the Elasticsearch
            index, if not set, dynamic mapping is applied.
        :param size: Maximal number of documents to import. If it is not set, all
            documents will be imported.
        """
        if mapping_path is not None:
            with open(mapping_path) as f:
                mapping = json.load(f)
        else:
            mapping = None
        with ElasticsearchConnector(
            connection_str=connection_str, connection_args=connection_args
        ) as es_connector:
            create_es_index(es_connector, index_name, mapping=mapping)
            corpus = self._corpus if size is None else self._corpus[:size]
            es_insert(es_connector, index_name, corpus)

    def _parse_corpus_file(self):
        if self._filepath.suffix == '.gz':
            f = gzip.open(self._filepath, 'rt', encoding='utf-8')
        elif self._filepath.suffix == '.jsonl':
            f = open(self._filepath)
        else:
            raise ValueError(
                'Expect the corpus file to have a .gz or .jsonl extension instead of'
                f'the extension "{self._filepath.suffix}"'
            )

        corpus = list()
        for line in f:
            json_obj = json.loads(line)
            corpus.append(json_obj)
        f.close()
        return corpus
