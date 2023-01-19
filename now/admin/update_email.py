import requests

from now.admin.utils import get_default_request_body

#  TODO needs to be updated to work on cli / or even putting things like this into a new client package


def update_emails(emails, remote_host):
    url = f"https://nowrun.jina.ai/api/v1"  # remote
    # url = f'http://localhost:8080/api/v1'  # for local testing
    request_body = get_default_request_body(secured=True, host=remote_host)
    # request_body['host'] = f'grpc://0.0.0.0'  # for local testing
    # request_body['port'] = 9090  # for local testing
    request_body['user_emails'] = emails
    response = requests.post(
        f'{url}/admin/updateUserEmails',
        json=request_body,
    )


if __name__ == '__main__':
    update_emails(
        emails=['hoenicke.florian@gmail.com'],
        remote_host='grpc://0.0.0.0',
    )
