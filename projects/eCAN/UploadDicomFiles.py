#!/usr/bin/env python3

# Orthanc - A Lightweight, RESTful DICOM Store
# Copyright (C) 2012-2016 Sebastien Jodogne, Medical Physics
# Department, University Hospital of Liege, Belgium
# Copyright (C) 2017-2023 Osimis S.A., Belgium
# Copyright (C) 2024-2024 Orthanc Team SRL, Belgium
# Copyright (C) 2021-2024 Sebastien Jodogne, ICTEAM UCLouvain, Belgium
#
# This program is free software: you can redistribute it and/or
# modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.


import base64
import httplib2
import json
import os
import os.path
import sys

dicom_count = 0
json_count = 0
total_file_count = 0


def IsJson(content):
    try:
        if (sys.version_info >= (3, 0)):
            json.loads(content.decode())
            return True
        else:
            json.loads(content)
            return True
    except:
        return False


# This function will upload a single file to Orthanc through the REST API
def UploadFile(URL, path, username, password):
    global dicom_count
    global json_count
    global total_file_count

    f = open(path, 'rb')
    content = f.read()
    f.close()
    total_file_count += 1

    sys.stdout.write('Importing %s' % path)

    if IsJson(content):
        sys.stdout.write(' => ignored JSON file\n')
        json_count += 1
        return

    try:
        h = httplib2.Http()

        headers = { 'content-type' : 'application/dicom' }

        if username != None and password != None:
            # h.add_credentials(username, password)

            # This is a custom reimplementation of the
            # "Http.add_credentials()" method for Basic HTTP Access
            # Authentication (for some weird reason, this method does
            # not always work)
            # http://en.wikipedia.org/wiki/Basic_access_authentication
            creds_str = username + ':' + password
            creds_str_bytes = creds_str.encode('ascii')
            creds_str_bytes_b64 = b'Basic ' + base64.b64encode(creds_str_bytes)
            headers['authorization'] = creds_str_bytes_b64.decode('ascii')

        resp, content = h.request(URL, 'POST', 
                                  body = content,
                                  headers = headers)

        if resp.status == 200:
            sys.stdout.write(' => success\n')
            dicom_count += 1
        else:
            sys.stdout.write(' => failure (Is it a DICOM file? Is there a password?)\n')

    except:
        type, value, traceback = sys.exc_info()
        sys.stderr.write(str(value))
        sys.stdout.write(' => unable to connect (Is Orthanc running? Is there a password?)\n')

def UploadDataset(orthanc_ip, orthanc_port, dataset_path, username, password):

    URL = 'http://%s:%d/instances' % (orthanc_ip, orthanc_port)

    print("PACS URL: " +  URL)

    if os.path.isfile(dataset_path):
        # Upload a single file
        UploadFile(URL, dataset_path, username, password)
    else:
        # Recursively upload a directory
        for root, dirs, files in os.walk(dataset_path):
            for f in files:
                    UploadFile(URL, os.path.join(root, f), username, password)
                    # Remove the file after it has been uploaded
                    os.remove(os.path.join(root, f))


    if dicom_count + json_count == total_file_count:
        print('\nSUCCESS: %d DICOM file(s) have been successfully imported' % dicom_count)
    else:
        print('\nWARNING: Only %d out of %d file(s) have been successfully imported as DICOM instance(s)' % (dicom_count, total_file_count - json_count))

    if json_count != 0:
        print('NB: %d JSON file(s) have been ignored' % json_count)

    print('')