import string

from py_noir.api_service import get
from py_noir.security.shanoir_context import ShanoirContext

"""
Define methods for Shanoir datasets MS execution monitoring API call
"""

ENDPOINT = '/datasets/execution-monitoring'
def get_execution_monitoring(context: ShanoirContext, monitoring_id: string):
    """ Get ExecutionMonitoring [monitoring_id]
    :param monitoring_id:
    :param context:
    :return: json
    """

    path = ENDPOINT + '/' + str(monitoring_id)
    response = get(context, path)
    return response.json()
