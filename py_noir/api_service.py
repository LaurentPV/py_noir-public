import logging
import string
from typing import re

import requests

from py_noir.security.authentication_service import ask_access_token, refresh_access_token
from py_noir.security.shanoir_context import ShanoirContext

"""
Define methods for generic API call
"""


def rest_request(context: ShanoirContext, method: string, path, **kwargs):
    """ Execute a [method] HTTP query to [path] endpoint
    :param context:
    :param method:
    :param path:
    :param kwargs:
    :return:
    """
    url = context.scheme + "://" + context.domain + "/shanoir-ng" + path

    response = None
    if method == 'get':
        response = requests.get(url, proxies=context.proxies, verify=context.verify, timeout=context.timeout, **kwargs)
    elif method == 'post':
        response = requests.post(url, proxies=context.proxies, verify=context.verify, timeout=context.timeout, **kwargs)
    elif method == 'put':
        response = requests.put(url, proxies=context.proxies, verify=context.verify, timeout=context.timeout, **kwargs)
    else:
        print('Error: unimplemented request type')

    return response


# perform a request on the given path, asks for a new access token if the current one is outdated
def request(context: ShanoirContext, method, path, raise_for_status=True, **kwargs):
    """ Authenticate / Re-authenticate user [context.username] and execute a [method] HTTP query to [path] endpoint
    :param context:
    :param method:
    :param path:
    :param raise_for_status:
    :param kwargs:
    :return:
    """
    if context.access_token is None:
        context = ask_access_token(context)
    headers = get_http_headers(context)

    response = rest_request(context, method, path, headers=headers, **kwargs)

    # if token is outdated, refresh it and try again
    if response.status_code == 401:
        context = refresh_access_token(context)
        headers = get_http_headers(context)
        response = rest_request(context, method, path, headers=headers, **kwargs)

    if raise_for_status:
        response.raise_for_status()

    return response


def get_http_headers(context: ShanoirContext):
    """ Set HTTP headers with [context.access_token]
    :param context: ShanoirContext
    :return:
    """
    headers = {
        'Authorization': 'Bearer ' + context.access_token,
        'content-type': 'application/json',
        'charset': 'utf-8'
    }
    return headers


# perform a GET request on the given url, asks for a new access token if the current one is outdated
def get(context: ShanoirContext, path: string, params=None, stream=None):
    """ Perform a GET HTTP request on [path] endpoint with given [params]
    :param context: ShanoirContext
    :param path: string
    :param params:
    :param stream:
    :return:
    """
    return request(context, 'get', path, params=params, stream=stream)


def post(context: ShanoirContext, path: string, params=None, files=None, stream=None, json=None, data=None,
         raise_for_status=True):
    """ Perform a POST HTTP request on [path] endpoint with given [params]/[files]/[stream] /[data]
    :param context:
    :param path:
    :param params:
    :param files:
    :param stream:
    :param json:
    :param data:
    :param raise_for_status:
    :return:
    """
    return request(context, 'post', path, raise_for_status, params=params, files=files, stream=stream, json=json,
                   data=data)


def put(context: ShanoirContext, path: string, params=None, files=None, stream=None, json=None, data=None,
        raise_for_status=True):
    """ Perform a PUT HTTP request on [path] endpoint with given [params]/[files]/[stream] /[data]
    :param context:
    :param path:
    :param params:
    :param files:
    :param stream:
    :param json:
    :param data:
    :param raise_for_status:
    :return:
    """
    return request(context, 'put', path, raise_for_status, params=params, files=files, stream=stream, json=json,
                   data=data)


try:
    from tqdm import tqdm


    def download_file(output_folder, response):
        filename = get_filename_from_response(output_folder, response)
        if not filename:
            return
        total = int(response.headers.get('content-length', 0))
        with open(filename, 'wb') as file, tqdm(
                desc=filename,
                total=total,
                unit='iB',
                unit_scale=True,
                unit_divisor=1024,
        ) as bar:
            for data in response.iter_content(chunk_size=1024):
                size = file.write(data)
                bar.update(size)

except ImportError as e:

    def download_file(output_folder, response):
        filename = get_filename_from_response(output_folder, response)
        if not filename:
            return
        open(filename, 'wb').write(response.content)
        return


def get_filename_from_response(output_folder, response):
    """ Build file path with [output_folder] and [response] 'Content-Disposition' header
    :param output_folder:
    :param response:
    :return:
    """
    filename = None
    if response.headers and 'Content-Disposition' in response.headers:
        filenames = re.findall('filename=(.+)', response.headers['Content-Disposition'])
        filename = str(output_folder / filenames[0]) if len(filenames) > 0 else None
    if filename is None:
        raise Exception('Could not find file name in response header', response.status_code, response.reason,
                        response.error, response.headers, response)
    return filename


def log_response(e):
    logging.error('Response status code: {e.response.status_code}')
    logging.error('		 reason: {e.response.reason}')
    logging.error('		 text: {e.response.text}')
    logging.error('		 headers: {e.response.headers}')
    logging.error(str(e))
    return
