FROM jinaai/jina:3.13.2-dev34-py38-standard

RUN apt-get update && apt-get install -y git &&\
    apt-get -y install build-essential libgomp1 libgl1-mesa-glx libglib2.0-0 libsm6 libxext6 libxrender-dev && \
    rm -rf /var/cache/apt/*

## install requirements for the executor
COPY requirements.txt .
RUN pip install --compile -r requirements.txt

# install latest code changes of the now repo without the requirements installed already
RUN pip install git+https://github.com/jina-ai/now@JINA_NOW_COMMIT_SHA --no-dependencies

# setup the workspace
COPY . /workdir/
WORKDIR /workdir

ENTRYPOINT ["jina", "executor", "--uses", "config.yml"]