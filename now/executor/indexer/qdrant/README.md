# NOWQdrantIndexer16

`NOWQdrantIndexer16` indexes Documents into a `DocumentArray`  using `storage='qdrant'`. Underneath, the `DocumentArray`  uses 
 [qdrant](https://github.com/qdrant/qdrant) to store and search Documents efficiently. 

The indexer relies on `DocumentArray` as a client for Qdrant, you can read more about the integration here: 
https://docarray.jina.ai/advanced/document-store/qdrant/

## Setup
`NOWQdrantIndexer16` requires a running Qdrant server. Make sure a server is up and running and your indexer is configured 
to use it before starting to index documents. For quick testing, you can run a containerized version locally using 
docker-compose :

```shell
docker-compose -f tests/docker-compose.yml up -d
```


Note that if you run a `Qdrant` service locally and try to run the `NOWQdrantIndexer16` via `docker`, you 
have to specify `'host': 'host.docker.internal'` instead of `localhost`, otherwise the client will not be 
able to reach the service from within the container.

## Usage

#### via Docker image (recommended)

```python
from jina import Flow
from docarray import Document
import numpy as np
	
f = Flow().add(
    uses='jinahub+docker://NOWQdrantIndexer16',
    uses_with={
        'host': 'localhost',
        'port': 6333,
        'collection_name': 'collection_name',
        'distance': 'cosine',
        'n_dim': 256,
    }
)

with f:
    f.post('/index', inputs=[Document(embedding=np.random.rand(256)) for _ in range(3)])
```

#### via source code

```python
from jina import Flow
from docarray import Document
	
f = Flow().add(uses='jinahub://NOWQdrantIndexer16',
    uses_with={
        'host': 'localhost',
        'port': 6333,
        'collection_name': 'collection_name',
        'distance': 'cosine',
        'n_dim': 256,
    }
)

with f:
    f.post('/index', inputs=[Document(embedding=np.random.rand(256)) for _ in range(3)])
```



## CRUD Operations

You can perform CRUD operations (create, read, update and delete) using the respective endpoints:

- `/index`: Add new data to Qdrant. 
- `/search`: Query the Qdrant index (created in `/index`) with your Documents.
- `/update`: Update Documents in Qdrant.
- `/delete`: Delete Documents in Qdrant.


## Vector Search

The following example shows how to perform vector search using`f.post(on='/search', inputs=[Document(embedding=np.array([1,1]))])`.


```python
from jina import Flow
from docarray import Document

f = Flow().add(
         uses='jinahub://NOWQdrantIndexer16',
         uses_with={'collection_name': 'test', 'n_dim': 2},
     )

with f:
    f.post(
        on='/index',
        inputs=[
            Document(id='a', embedding=np.array([1, 3])),
            Document(id='b', embedding=np.array([1, 1])),
        ],
    )

    docs = f.post(
        on='/search',
        inputs=[Document(embedding=np.array([1, 1]))],
    )

# will print "The ID of the best match of [1,1] is: b"
print('The ID of the best match of [1,1] is: ', docs[0].matches[0].id)
```

### Using filtering
To do filtering with the NOWQdrantIndexer16 you should first define columns and precise the dimension of your embedding space.
For instance :

```python
from jina import Flow

f = Flow().add(
    uses='jinahub+docker://NOWQdrantIndexer16',
    uses_with={
        'collection_name': 'test',
        'n_dim': 3,
        'columns': [('price', 'float')],
    },
)


```

Then you can pass a filter as a parameters when searching for document:
```python
from docarray import Document, DocumentArray
import numpy as np

docs = DocumentArray(
    [
        Document(id=f'r{i}', embedding=np.random.rand(3), tags={'price': i})
        for i in range(50)
    ]
)


filter_ = {'must': [{'key': 'price', 'range': {'gte': 30}}]}

with f:
    f.index(docs)
    doc_query = DocumentArray([Document(embedding=np.random.rand(3))])
    f.search(doc_query, parameters={'filter': filter_})
```

For more information please refer to the docarray [documentation](https://docarray.jina.ai/advanced/document-store/qdrant/#vector-search-with-filter)