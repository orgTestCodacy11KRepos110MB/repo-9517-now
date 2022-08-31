import itertools
import math
import os
from inspect import getmembers, isclass
from typing import Any, Dict, List, Optional, Tuple

from dask.distributed import Client
from docarray import Document, DocumentArray

from now.finetuning import generation_fns
from now.finetuning.generation_fns import GeneratorFunction
from now.now_dataclasses import Task, TrainDataGenerationConfig


class EncoderDataBuilder:
    def __init__(
        self,
        name: str,
        methods: List[TrainDataGenerationConfig],
        encoder_type: str,
    ):
        """
        Fine-tuning data generation for a specific encoder.

        :param name: Name of the encoder.
        :param methods: List of methods to generate fine-tuning data.
        :param encoder_type: Type of the encoder, either `single_model`
            or `multi_model`.
        """
        self._name = name
        self._methods = methods
        self._encoder_type = encoder_type
        self._generation_cls = {
            cls.name(): cls
            for _, cls in getmembers(generation_fns, isclass)
            if issubclass(cls, GeneratorFunction)
        }

    def build(self, es_data: List[Dict[str, Any]]) -> DocumentArray:
        """
        Generates query and target data based on method(s).

        In case the encoder is `single_model`, we save generated targets and queries
        separately. If the encoder is `multi_model`, we generate query-target pairs.

        :param es_data: Data extracted from ES.
        :return: `DocumentArray` of generated data.
        """
        data = DocumentArray()
        for method in self._methods:
            query_generator = self._generation_cls[method.query.method](
                scope=method.query.scope, **method.query.parameters
            )
            target_generator = self._generation_cls[method.target.method](
                scope=method.target.scope, **method.target.parameters
            )
            for doc_id, document in enumerate(es_data):
                queries = query_generator.process(document=document)
                targets = target_generator.process(document=document)
                if self._encoder_type == 'single_model':
                    merged_docs = []
                    for doc in [*queries, *targets]:
                        doc.tags = {'finetuner_label': doc_id}
                        merged_docs.append(doc)
                    data.extend(merged_docs)
                else:
                    data.extend(
                        [
                            Document(chunks=[query, target])
                            for query, target in itertools.product(queries, targets)
                        ]
                    )
        return data

    @property
    def name(self):
        return self._name


class ESDataTransformer:
    @classmethod
    def transform(cls, data: DocumentArray) -> List[Dict[str, Any]]:
        """
        Transform data extracted from Elasticsearch to a more convenient form.

        :param data: Loaded `DocumentArray` containing ES data.
        :return: List of data examples as dictionaries.
        """
        transformed_data = []
        for document in data:
            attributes = {}
            cls._transform_doc(document, attributes, [])
            transformed_data.append(attributes)
        return transformed_data

    @classmethod
    def _transform_doc(
        cls, document: Document, attributes: Dict[str, Any], names: List[str]
    ):
        """
        Extract attributes from a `Document` and store it as a dictionary.

        Recursively iterates across different chunks of the `Document` and collects
        attributes with their corresponding values.

        :param document: `Document` we want to transform.
        :param attributes: Dictionary of attributes extracted from the document.
        :param names: Name of an attribute (attribute names may be nested, e.g.
            info.cars, and we need to store name(s) on every level of recursion).
        """
        if not document.chunks:
            names.append(document.tags['field_name'])
            attr_name = '.'.join(names)
            attr_val = (
                document.text if document.tags['modality'] == 'text' else document.uri
            )
            if attr_name not in attributes:
                attributes[attr_name] = []
            attributes[attr_name].append(attr_val)
        else:
            if 'field_name' in document.tags:
                names.append(document.tags['field_name'])
            for doc in document.chunks:
                cls._transform_doc(doc, attributes, names[:])


class DataBuilder:
    def __init__(
        self,
        dataset: DocumentArray,
        config: Task,
        num_workers: Optional[int] = None,
        threads_per_worker: Optional[int] = 4,
    ):
        """
        Fine-tuning data generation for a specific task.

        :param dataset: A `DocumentArray` extracted from ES.
        :param config: A `TaskConfig` object containing information about
            data generation methods.
        :param num_workers: Number of workers for data generation.
        :param threads_per_worker: Number of threads per worker.
        """
        self._dataset = dataset
        self._num_workers = num_workers if num_workers else os.cpu_count()
        self._enc_data_builders = self._init_enc_data_builders(config)
        self._dask_client = Client(
            threads_per_worker=threads_per_worker,
            n_workers=self._num_workers,
        )

    @staticmethod
    def _init_enc_data_builders(
        config: Task,
    ) -> List[Tuple[str, EncoderDataBuilder]]:
        """
        Initialize data builders for encoder(s).

        These builders will be used when `DataGenerator.build()` is called.

        :param config: A `TaskConfig` object containing information about ES data and
            data generation approaches.
        :return: List of pairs - intended dataset name and `EncoderDataBuilder`.
        """
        return [
            (
                encoder.train_dataset_name,
                EncoderDataBuilder(
                    name=encoder.name,
                    methods=encoder.training_data_generation_methods,
                    encoder_type='multi_model'
                    if encoder.encoder_type == 'text-to-image'
                    else 'single_model',
                ),
            )
            for encoder in config.encoders
        ]

    @staticmethod
    def _data_chunk_generator(data: DocumentArray, num_chunks: int) -> DocumentArray:
        """Generates chunks of ES data for parallel data generation.

        :param data: ES data.
        :param num_chunks: number of chunks to be generated.
        :return: Data chunk as a `DocumentArray`.
        """
        chunk_size = math.ceil(len(data) / num_chunks)
        for pos in range(0, len(data), chunk_size):
            yield data[pos : pos + chunk_size]  # noqa: E203

    def build(
        self,
        to_hubble: bool = False,
        data_dir: Optional[str] = None,
    ) -> Dict[str, DocumentArray]:
        """
        Generates data from ES dataset based on the task configuration file.

        You can also upload the generated data on hubble, or save it locally
        (or both).

        :param to_hubble: Uploads data to Hubble if `True`.
        :param data_dir: Saves data locally in the given directory if it's not `None`.
        :return: Generated data for each encoder.
        """

        def _generate(data: DocumentArray, data_builder: EncoderDataBuilder):
            transformed_data = ESDataTransformer.transform(data)
            return data_builder.build(es_data=transformed_data)

        data = {}
        for dataset_name, enc_data_builder in self._enc_data_builders:
            futures = []
            for chunk in self._data_chunk_generator(
                data=self._dataset, num_chunks=self._num_workers
            ):
                futures.append(
                    self._dask_client.submit(_generate, chunk, enc_data_builder)
                )
            results = self._dask_client.gather(futures)
            dataset = DocumentArray(itertools.chain.from_iterable(results))
            data[enc_data_builder.name] = dataset

            if to_hubble:
                dataset.push(dataset_name, show_progress=True, public=False)
            if data_dir:
                os.makedirs(data_dir, exist_ok=True)
                dataset.save_binary(os.path.join(data_dir, dataset_name))
        return data
