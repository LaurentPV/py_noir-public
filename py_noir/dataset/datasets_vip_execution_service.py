import datetime

import json
import time

from py_noir.api_service import post, get
from py_noir.security.shanoir_context import ShanoirContext

"""
Define methods for Shanoir datasets MS execution API call
"""

ENDPOINT = 'datasets/vip/execution/'
LOG_FILE = 'datasets_status.csv'


def create_execution(context: ShanoirContext, execution: dict):
    path = ENDPOINT
    response = post(context, path, {}, data=json.dumps(execution), raise_for_status=False)
    return response.json()


def create_executions(context: ShanoirContext, executions: list[dict], log_status=False):
    """
    Create executions [executions] in queue.
    Log status in [context.output_folder] if [log_status] is True
    :param context:
    :param executions:
    :param log_status:
    """
    if log_status and context.output_folder is None:
        print("Status logging is on but output folder is not set")
        log_status = False

    if log_status:
        log_file = open(LOG_FILE, "w")
        log_file.write("monitoring_id;execution_name;status")
        log_file.close()

    for execution in executions:
        print(execution)
        monitoring = create_execution(context, execution)
        identifier = monitoring['id']
        status = 'RUNNING'
        while status == 'RUNNING':
            time.sleep(10)
            status = get_execution_status(context, identifier)

        if log_status:
            log_file = open(LOG_FILE, "a")
            log_file.write(monitoring["id"] + ";" + execution["name"] + ";" + status)
            log_file.close()

    print("All executions finished")


def get_execution_status(context: ShanoirContext, identifier):
    path = ENDPOINT + '/' + identifier + '/status'
    response = get(context, path)
    return response.content
