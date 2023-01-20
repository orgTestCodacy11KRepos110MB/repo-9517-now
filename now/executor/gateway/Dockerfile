FROM jinaai/jina:3.13.2-dev34-py38-standard
#FROM nginx:latest


RUN apt-get update && apt-get install --no-install-recommends -y git pip nginx && rm -rf /var/lib/apt/lists/*

## install requirements for the executor
COPY requirements.txt .
RUN pip install --compile -r requirements.txt

# install latest code changes of the now repo without the requirements installed already
RUN pip install git+https://github.com/jina-ai/now@780cd9a58dc65b02a5f359f7babbbc9aa0cd2a90

# RUN pip install "jina==3.13.2.dev34"
RUN pip install -U git+https://github.com/jina-ai/jina@master

# setup the workspace
COPY . /workdir/
WORKDIR /workdir

## run nginx.conf
COPY nginx.conf nginx.conf
#COPY nginx.conf /etc/nginx/nginx.conf


#CMD ["nginx", "-g", "daemon off &&"]

#ENTRYPOINT ["nginx", "-g", "daemon off &&", "jina", "gateway", "--uses", "config.yml"]
ENTRYPOINT ["jina", "gateway", "--uses", "config.yml"]
