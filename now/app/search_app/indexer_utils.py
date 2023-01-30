import pathlib
import time

from now.deployment.deployment import cmd


def setup_elastic_service(
    kubectl_path: str,
) -> str:
    """Setup ElasticSearch service and return a connection string to connect to the service with.

    :param kubectl_path: path to kubectl binary
    :return: connection string for connecting to the ElasticSearch service.
    """
    MAX_RETRIES = 20
    cur_dir = pathlib.Path(__file__).parent.resolve()
    cmd(
        f'{kubectl_path} create -f https://download.elastic.co/downloads/eck/2.4.0/crds.yaml'
    )
    cmd(
        f'{kubectl_path} apply -f https://download.elastic.co/downloads/eck/2.4.0/operator.yaml'
    )
    cmd(f'{kubectl_path} create ns nowapi')
    cmd(f'{kubectl_path} apply -f {cur_dir}/../deployment/elastic_kind.yml')
    num_retries = 0
    es_password, error_msg = '', b''
    while num_retries < MAX_RETRIES:
        es_password, error_msg = cmd(
            [
                kubectl_path,
                "get",
                "secret",
                "quickstart-es-elastic-user",
                "-o",
                "go-template='{{.data.elastic | base64decode}}'",
            ]
        )
        if es_password:
            es_password = es_password.decode("utf-8")[1:-1]
            break
        else:
            num_retries += 1
            time.sleep(2)
    if not es_password:
        raise Exception(error_msg.decode("utf-8"))
    host = f"https://elastic:{es_password}@quickstart-es-http.default:9200"
    return host
