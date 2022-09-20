import subprocess
from collections import defaultdict
from time import sleep
from typing import Dict, List, Optional, Tuple, Union

from docarray import DocumentArray
from jina import Executor, requests
from jina.logging.logger import JinaLogger


class QdrantIndexer3(Executor):
    """QdrantIndexer3 indexes Documents into a Qdrant server using DocumentArray  with `storage='qdrant'`"""

    def __init__(
        self,
        host: str = 'localhost',
        port: int = 6333,
        collection_name: str = 'Persisted',
        distance: str = 'cosine',
        dim: int = 512,
        ef_construct: Optional[int] = None,
        full_scan_threshold: Optional[int] = None,
        m: Optional[int] = None,
        scroll_batch_size: int = 64,
        serialize_config: Optional[Dict] = None,
        columns: Optional[Union[List[Tuple[str, str]], Dict[str, str]]] = None,
        **kwargs,
    ):
        """
        :param host: Hostname of the Qdrant server
        :param port: port of the Qdrant server
        :param collection_name: Qdrant Collection name used for the storage
        :param distance: The distance metric used for the vector index and vector search
        :param n_dim: number of dimensions
        :param ef_construct: The size of the dynamic list for the nearest neighbors (used during the construction).
            Controls index search speed/build speed tradeoff. Defaults to the default `ef_construct` in the Qdrant
            server.
        :param full_scan_threshold: Minimal amount of points for additional payload-based indexing. Defaults to the
            default `full_scan_threshold` in the Qdrant server.
        :param scroll_batch_size: batch size used when scrolling over the storage.
        :param serialize_config: DocumentArray serialize configuration.
        :param m: The maximum number of connections per element in all layers. Defaults to the default
            `m` in the Qdrant server.
        :param columns: precise columns for the Indexer (used for filtering).
        """
        super().__init__(**kwargs)
        # if qdrant exists, then start it
        try:
            process = subprocess.Popen(['./run-qdrant.sh'])
            sleep(3)
            self.logger.info('Qdrant server started')
        except FileNotFoundError:
            self.logger.info('Qdrant not found, locally. So it won\'t be started.')

        # TODO: remove this hack
        columns = {'title': '<this value is not used>'}
        self._index = DocumentArray(
            storage='qdrant',
            config={
                'collection_name': collection_name,
                'host': host,
                'port': port,
                'n_dim': dim,
                'distance': distance,
                'ef_construct': ef_construct,
                'm': m,
                'scroll_batch_size': scroll_batch_size,
                'full_scan_threshold': full_scan_threshold,
                'serialize_config': serialize_config or {},
                'columns': columns,
            },
        )

        self.logger = JinaLogger(self.metas.name)

    @requests(on='/index')
    def index(self, docs: DocumentArray, **kwargs):
        """Index new documents
        :param docs: the Documents to index
        """
        # for the experiment, we don't need blobs in the root and chunk level also, we set traversal_paths to '@c'
        docs = docs['@c']
        for d in docs:
            d.blob = None
        # qdrant needs a list of values when filtering on sentences
        for d in docs:
            d.tags['title'] = d.tags['title'].split()
        self._index.extend(docs)
        #  prevent sending the data back by returning an empty DocumentArray
        return DocumentArray()

    @requests(on='/search')
    def search(
        self,
        docs: 'DocumentArray',
        parameters: Dict = {},
        **kwargs,
    ):
        """Perform a vector similarity search and retrieve the full Document match

        :param docs: the Documents to search with
        :param parameters: Dictionary to define the `filter` that you want to use.
        :param kwargs: additional kwargs for the endpoint

        """

        # docs = docs[traversal_paths]
        # filtered_docs = self.filter_docs(self.index[traversal_paths], parameters)
        #
        # match_limit = limit
        # if traversal_paths == "@c":
        #     match_limit = limit * 3 * 100000
        # docs.match(filtered_docs, limit=match_limit)
        # if traversal_paths == "@c":
        #     if ranking_method == "min":
        #         self.merge_matches_min(docs, limit)
        #     elif ranking_method == "sum":
        #         self.merge_matches_sum(docs, limit)
        # return docs
        docs = docs["@c"]
        filter = {'must': [{'key': 'title', 'match': {'value': docs[0].text}}]}
        docs.match(self._index, filter=filter, limit=180)
        self.merge_matches_sum(docs, 60)
        return docs

    @requests(on='/delete')
    def delete(self, parameters: Dict, **kwargs):
        """Delete entries from the index by id

        :param parameters: parameters of the request

        Keys accepted:
            - 'ids': List of Document IDs to be deleted
        """
        deleted_ids = parameters.get('ids', [])
        if len(deleted_ids) == 0:
            return
        del self._index[deleted_ids]

    @requests(on='/update')
    def update(self, docs: DocumentArray, **kwargs):
        """Update existing documents
        :param docs: the Documents to update
        """

        for doc in docs:
            try:
                self._index[doc.id] = doc
            except IndexError:
                self.logger.warning(
                    f'cannot update doc {doc.id} as it does not exist in storage'
                )

    @requests(on='/filter')
    def filter(self, parameters: Dict, **kwargs):
        """
        Query documents from the indexer by the filter `query` object in parameters. The `query` object must follow the
        specifications in the `find` method of `DocumentArray` in the docs https://docarray.jina.ai/fundamentals/documentarray/find/#filter-with-query-operators
        :param parameters: parameters of the request
        """
        return self._index.find(parameters['query'])

    @requests(on='/fill_embedding')
    def fill_embedding(self, docs: DocumentArray, **kwargs):
        """Fill embedding of Documents by id

        :param docs: DocumentArray to be filled with Embeddings from the index
        """
        for doc in docs:
            doc.embedding = self._index[doc.id].embedding

    @requests(on='/clear')
    def clear(self, **kwargs):
        """Clear the index"""
        self._index.clear()

    def close(self) -> None:
        super().close()
        del self._index

    def merge_matches_sum(self, docs, limit):
        # in contrast to merge_matches_min, merge_matches_avg sorts the parent matches by the average distance of all chunk matches
        # we have 3 chunks indexed for each root document but the matches might contain less than 3 chunks
        # in case of less than 3 chunks, we assume that the distance of the missing chunks is the same to the last match
        # m.score.value is a distance metric
        for d in docs:
            parent_id_count_and_sum_and_chunks = defaultdict(lambda: [0, 0, []])
            for m in d.matches:
                count_and_sum_and_chunks = parent_id_count_and_sum_and_chunks[
                    m.parent_id
                ]
                distance = m.scores['cosine'].value
                count_and_sum_and_chunks[0] += 1
                count_and_sum_and_chunks[1] += distance
                count_and_sum_and_chunks[2].append(m)
            all_matches = []
            for group in (3, 2, 1):
                parent_id_to_sum_and_chunks = {
                    parent_id: count_and_sum_and_chunks[1:]
                    for parent_id, count_and_sum_and_chunks in parent_id_count_and_sum_and_chunks.items()
                    if count_and_sum_and_chunks[0] == group
                }
                parent_to_sum_sorted = sorted(
                    parent_id_to_sum_and_chunks.items(), key=lambda x: x[1][0]
                )
                matches = [
                    sum_and_chunks[1][0]
                    for parent_id, sum_and_chunks in parent_to_sum_sorted
                ]
                all_matches.extend(matches)
                print(f'# num parents for group {group}: {len(matches)}')
            d.matches = all_matches[:limit]
