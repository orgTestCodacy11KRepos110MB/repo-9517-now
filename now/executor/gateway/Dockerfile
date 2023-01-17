FROM jinaai/jina:3-py38-perf

RUN apt-get update && apt-get install --no-install-recommends -y git && rm -rf /var/lib/apt/lists/*

## install requirements for the executor
COPY requirements.txt .
RUN pip install --compile -r requirements.txt

# install latest code changes of the now repo without the requirements installed already
RUN pip install git+https://github.com/jina-ai/now@JINA_NOW_COMMIT_SHA --no-dependencies

# setup the workspace
COPY . /workdir/
WORKDIR /workdir

ENTRYPOINT ["jina", "executor", "--uses", "config.yml"]
