import string

from py_noir.api_service import get, download_file, post
from py_noir.security.shanoir_context import ShanoirContext

"""
Define methods for Shanoir studies MS subject API call
"""

ENDPOINT = '/studies/subjects'


def find_subject_ids_by_study_id(context: ShanoirContext, study_id):
    """ Get all subjects from study [study_id]
    :param context:
    :param study_id:
    :return:
    """
    print('Getting subjects from study', study_id)
    path = ENDPOINT + '/' + study_id + '/allSubjects'
    response = get(context, path)
    return response.json()