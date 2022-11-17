import asyncio
import subprocess
import tempfile

from jcloud.flow import CloudFlow


def deploy_wolf(path: str):
    return CloudFlow(path=path).__enter__()


def terminate_wolf(flow_id: str):
    CloudFlow(flow_id=flow_id).__exit__()


def status_wolf(flow_id):
    loop = get_or_create_eventloop()
    return loop.run_until_complete(CloudFlow(flow_id=flow_id).status)


def get_or_create_eventloop():
    try:
        return asyncio.get_event_loop()
    except RuntimeError as ex:
        if "There is no current event loop in thread" in str(ex):
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            return asyncio.get_event_loop()


def list_all_wolf(status='Serving', namespace='nowapi'):
    loop = get_or_create_eventloop()
    flows = loop.run_until_complete(CloudFlow().list_all(phase=status))
    if flows is None:
        return []
    # filter by namespace - if the namespace is contained in the flow name
    if namespace:
        return [f for f in flows if namespace in f['name']]
    return flows


def cmd(command, std_output=False, wait=True):
    if isinstance(command, str):
        command = command.split()
    if not std_output:
        process = subprocess.Popen(
            command, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
    else:
        process = subprocess.Popen(command)
    if wait:
        output, error = process.communicate()
        return output, error


def which(executable: str) -> bool:
    return bool(cmd('which ' + executable)[0])


def apply_replace(f_in, replace_dict, kubectl_path):
    with open(f_in, "r") as fin:
        with tempfile.NamedTemporaryFile(mode='w') as fout:
            for line in fin.readlines():
                for key, val in replace_dict.items():
                    line = line.replace('{' + key + '}', str(val))
                fout.write(line)
            fout.flush()
            cmd(f'{kubectl_path} apply -f {fout.name}')
