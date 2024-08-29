import os

import requests
import json
import getpass
import sys
import logging
import http.client as http_client
from pathlib import Path

from py_noir.security.shanoir_context import ShanoirContext

"""
Define methods for Shanoir authentication
"""

ENDPOINT = '/auth/realms/shanoir-ng/protocol/openid-connect/token'

def init_logging(args):
    verbose = args.verbose

    logfile = Path(args.log_file)
    logfile.parent.mkdir(exist_ok=True, parents=True)

    logging.basicConfig(
        level=logging.INFO,  # if verbose else logging.ERROR,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[
            logging.FileHandler(str(logfile)),
            logging.StreamHandler(sys.stdout)
        ]
    )

    if verbose:
        http_client.HTTPConnection.debuglevel = 1

        requests_log = logging.getLogger("requests.packages.urllib3")
        requests_log.setLevel(logging.DEBUG)
        requests_log.propagate = True


def get_context_from_args(args) -> ShanoirContext:
    """ Build ShanoirContext from command line arguments
    :param args:
    :return:
    """
    context = ShanoirContext()

    context.domain = args.domain
    context.username = args.username

    init_logging(args)

    context.verify = args.certificate if hasattr(args, 'certificate') and args.certificate != '' else True

    proxy_url = None  # 'user:pass@host:port'

    if hasattr(args, 'proxy_url') and args.proxy_url is not None:
        proxy_a = args.proxy_url.split('@')
        proxy_user = proxy_a[0]
        proxy_host = proxy_a[1]
        proxy_password = getpass.getpass(
            prompt='Proxy password for user ' + proxy_user + ' and host ' + proxy_host + ': ', stream=None)
        proxy_url = proxy_user + ':' + proxy_password + '@' + proxy_host

    else:

        if hasattr(args, 'configuration_folder') and args.configuration_folder:
            configuration_folder = Path(args.configuration_folder)
        else:
            cfs = sorted(list(Path.home().glob('.su_v*')))
            configuration_folder = cfs[-1] if len(cfs) > 0 else Path().home()

        proxy_settings = configuration_folder / 'proxy.properties'

        proxy_config = {}

        if proxy_settings.exists():
            with open(proxy_settings) as file:
                for line in file:
                    if line.startswith('proxy.'):
                        line_s = line.split('=')
                        proxy_key = line_s[0]
                        proxy_value = line_s[1].strip()
                        proxy_key = proxy_key.split('.')[-1]
                        proxy_config[proxy_key] = proxy_value

                if 'enabled' not in proxy_config or proxy_config['enabled'] == 'true':
                    if 'user' in proxy_config and len(proxy_config['user']) > 0 and 'password' in proxy_config and len(
                            proxy_config['password']) > 0:
                        proxy_url = proxy_config['user'] + ':' + proxy_config['password']
                    proxy_url += '@' + proxy_config['host'] + ':' + proxy_config['port']
        else:
            print("Proxy configuration file not found. Proxy will be ignored.")

    if proxy_url:
        context.proxies = {
            'http': 'http://' + proxy_url,
            # 'https': 'https://' + proxy_url,
        }

    context.timeout = args.timeout

    return context


def ask_access_token(context: ShanoirContext) -> ShanoirContext:
    """ Prompt user [context.username] for password
    and set [context.access_token] & [context.refresh_token] from Shanoir auth API
    :param context:
    :return:
    """
    try:
        password = os.environ['shanoir_password'] if 'shanoir_password' in os.environ else getpass.getpass(
            prompt='Password for Shanoir user ' + context.username + ': ', stream=None)
    except:
        sys.exit(0)

    url = context.scheme + '://' + context.domain + ENDPOINT

    payload = {
        'client_id': context.clientId,
        'grant_type': 'password',
        'username': context.username,
        'password': password,
        'scope': 'offline_access'
    }
    # curl -d '{"client_id":"shanoir-uploader", "grant_type":"password", "username": "amasson", "password": "", "scope": "offline_access" }' -H "Content-Type: application/json" -X POST

    headers = {'content-type': 'application/x-www-form-urlencoded'}
    print('get keycloak token...')
    response = requests.post(url, data=payload, headers=headers, proxies=context.proxies, verify=context.verify,
                             timeout=context.timeout)
    if not hasattr(response, 'status_code') or response.status_code != 200:
        print('Failed to connect, make sur you have a certified IP or are connected on a valid VPN.')
        raise ConnectionError(response.status_code)

    response_json = json.loads(response.text)
    if 'error_description' in response_json and response_json['error_description'] == 'Invalid user credentials':
        print('bad username or password')
        sys.exit(1)

    context.refresh_token = response_json['refresh_token']
    context.access_token = response_json['access_token']

    return context


# get a new access token using the refresh token
def refresh_access_token(context: ShanoirContext) -> ShanoirContext:
    """ Set [context.access_token] from Shanoir auth API using [context.refresh_token]
    :param context:
    :return:
    """
    url = context.scheme + '://' + context.domain + ENDPOINT
    payload = {
        'grant_type': 'refresh_token',
        'refresh_token': context.refresh_token,
        'client_id': context.clientId
    }
    headers = {'content-type': 'application/x-www-form-urlencoded'}
    logging.info('refresh keycloak token...')
    response = requests.post(url, data=payload, headers=headers, proxies=context.proxies, verify=context.verify,
                             timeout=context.timeout)
    if response.status_code != 200:
        logging.error('response status : {response.status_code}, {responses[response.status_code]}')
    response_json = response.json()
    context.access_token = response_json['access_token']
    return context
