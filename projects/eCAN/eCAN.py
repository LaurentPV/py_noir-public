import os
import sys
import zipfile
import pydicom
from pydicom.uid import generate_uid
from pydicom import dcmread
from pynetdicom import AE
from pynetdicom.sop_class import MRImageStorage, XRayAngiographicImageStorage
import csv
import json
import argparse
from tqdm import tqdm
import shutil

sys.path.append( '../../')
sys.path.append( '../../py_noir/dataset')
from py_noir import api_service
from py_noir.dataset import datasets_solr_service
from py_noir.dataset.solr_query import SolrQuery
from py_noir.dataset.datasets_dataset_service import get_dataset_dicom_metadata, download_dataset, download_datasets

import projects.eCAN.UploadDicomFiles as UploadDicomFiles

# Distant PACS parameters
pacs_ae_title = 'ORTHANC'
pacs_ip = '127.0.0.1'
pacs_port = 4242
dicom_web_port = 8042

# Script AE parameters
listen_port = 45106
client_ae_title = 'ECAN_SCRIPT_AE'


def create_arg_parser(description="""Shanoir downloader"""):
  parser = argparse.ArgumentParser(prog=__file__, description=description, formatter_class=argparse.ArgumentDefaultsHelpFormatter)
  return parser

def add_username_argument(parser):
  parser.add_argument('-u', '--username', required=True, help='Your shanoir username.')

def add_domain_argument(parser):
  parser.add_argument('-d', '--domain', default='shanoir.irisa.fr', help='The shanoir domain to query.')

def add_common_arguments(parser):
  add_username_argument(parser)
  add_domain_argument(parser)

def add_configuration_arguments(parser):
  parser.add_argument('-c', '--configuration_folder', required=False, help='Path to the configuration folder containing proxy.properties (Tries to use ~/.su_vX.X.X/ by default). You can also use --proxy_url to configure the proxy (in which case the proxy.properties file will be ignored).')
  parser.add_argument('-pu', '--proxy_url', required=False, help='The proxy url in the format "user@host:port". The proxy password will be asked in the terminal. See --configuration_folder.')
  parser.add_argument('-ca', '--certificate', default='', required=False, help='Path to the CA bundle to use.')
  parser.add_argument('-v', '--verbose', default=False, action='store_true', help='Print log messages.')
  parser.add_argument('-t', '--timeout', type=float, default=60*4, help='The request timeout.')
  parser.add_argument('-lf', '--log_file', type=str, help="Path to the log file. Default is output_folder/downloads.log", default=None)
  parser.add_argument('-out', '--output_folder', type=str, help="Path to the result folder.", default=None)
  parser.add_argument('-s', '--study', required=False, type=str, help="Shanoir study to query (e.g UCAN).", default=None)
  return parser

def add_subjects_argument(parser):
  parser.add_argument('-subjects', '--subjects_csv', required=False, default='', help='Path to the list of subjects in a csv file') # !!! If not provided, all TOFS will be downloaded !!!
  return parser

def getDatasets(config, subjects_entries, study):
  query = SolrQuery()
  query.size = 100000
  query.expert_mode = True
  query.search_text = ""

  if study:
    query.search_text = query.search_text + "studyName:" + study + " AND "

  # If -subjects argument is filled, we filter the datasets by subjectName, otherwise we search for all TOF datasets
  if subjects_entries: 
    with open(str(subjects_entries), "r") as f:
      reader = csv.reader(f)
      subjects = [row[0].strip() for row in reader if row]
      query.search_text = ('subjectName:' + str(subjects)
                       .replace(',', ' OR ')
                       .replace('\'', '')
                       .replace("[", "(")
                       .replace("]", ")")
                       + ' AND ')

  # We filter the datasets by datasetName and sliceThickness directly to replace the check metadata step
  query.search_text = query.search_text + "datasetName:(*tof* OR *angio* OR *flight* OR *mra* OR *arm*) AND sliceThickness:([0.01 TO 5] OR [100 TO 500])"

  result = datasets_solr_service.solr_search(config, query)
  jsonresult = json.loads(result.content)

  dataset_ids = {}
  for dataset in tqdm(jsonresult["content"], desc="Filtering datasets"):
    ### We comment for now the check metadata step to skip one API call
    #metadata = get_dataset_dicom_metadata(config, dataset["datasetId"])
    # if checkMetaData(metadata):
    #   subName = dataset["subjectName"]
    #   if (subName not in dataset_ids):
    #     dataset_ids[subName] = []
    #   dataset_ids[dataset["subjectName"]].append(dataset["datasetId"])
    subName = dataset["subjectName"]
    if (subName not in dataset_ids):
      dataset_ids[subName] = []
    dataset_ids[dataset["subjectName"]].append(dataset["datasetId"])

  print("Number of Shanoir datasets to download: " + str(len(dataset_ids)))

  downloadDatasets(config, dataset_ids)

def checkMetaData(metadata):
  if metadata is None :
    return False
  mri_types = ["tof","angio","angiography","time of flight","mra"]
  slice_thickness = 0.6
  is_tof = False
  thin_enough = False
  enough_frames = False
  for item in metadata:
    # Check if ProtocolName or SeriesDescription contains "tof" or "angio" or "flight"
    if ('0008103E' in item and any(x in item['0008103E']["Value"][0].lower() for x in mri_types)) or ('00181030' in item and any(x in item['00181030']["Value"][0].lower() for x in mri_types)):
      is_tof = True

    # Check if SliceThickness is less than 0.5mm or between 100 and 500 (in case unity is not mm but um)
    if '00180050' in item and "Value" in item['00180050'] and (float(item['00180050']["Value"][0]) < slice_thickness or (float(item['00180050']["Value"][0]) > 99 and float(item['00180050']["Value"][0]) < slice_thickness*1000)):
      thin_enough = True

    # if ("20011018" in item and item["20011018"]["Value"] != [] and int(item["20011018"]["Value"][0]) > 50) or ("00280008" in item and item["00280008"]["Value"] != [] and int(item["00280008"]["Value"][0]) > 50) or ("07A11002" in item and item["07A11002"]["Value"] != [] and int(item["07A11002"]["Value"][0]) > 50):
    #   enough_frames = True
  return thin_enough and is_tof and enough_frames


def downloadDatasets(config, dataset_ids):
  # We store the progress in a json file
  progress = {}
  progress_file = os.path.join(config.output_folder, "progress.json")

  # Load existing progress if the file exists
  if os.path.exists(progress_file):
    with open(progress_file, 'r') as f:
      progress = json.load(f)
  else:
    with open(progress_file, "w") as file:
      json.dump(progress, file)

  for subject in tqdm(dataset_ids, desc="Downloading datasets"):
    subjFolder = config.output_folder + "/" + subject
    for dataset_id in dataset_ids[subject]:
      #download_datasets(config, dataset_ids[subject], 'dcm', subjFolder) ???
      outFolder = config.output_folder + "/" + subject + "/" + str(dataset_id)
      os.makedirs(outFolder, exist_ok=True)
      download_dataset(config, dataset_id, 'dcm', outFolder, True)
      # We send the dicom files to the PACS if the number of slices is greater than 49
      if count_slices(outFolder) > 49:
        # Setting a common FrameOfReferenceUID metadata for all instances of a serie
        set_frame_of_reference_UID(outFolder)
        UploadDicomFiles.UploadDataset(pacs_ip, dicom_web_port, outFolder, None, None)
        # C-Store the dicom files to the PACS
        # for file_name in tqdm(os.listdir(outFolder), desc="Sending DICOM files to PACS"):
        #   if file_name.endswith('.dcm'):
        #     cStore_dataset(os.path.join(outFolder, file_name), assoc)
        # If the dataset folder is empty it means that all .dcm files have been sent to the PACS
        if not os.listdir(outFolder):
          #print("Dataset " + str(dataset_id) + " has been successfully sent to the PACS")
          os.rmdir(outFolder)
          # Update progress
          update_progress(progress, subject, dataset_id, progress_file)
      else:
        shutil.rmtree(outFolder)
        # Update progress in case dataset not OK but still processed ???
        # update_progress(progress, subject, dataset_id, progress_file)
    # We remove the subject folder if it is empty
    if not os.listdir(subjFolder):
      os.rmdir(subjFolder)


### Function to retrieve the number of instances in a DICOM serie
def count_slices(directory):
    slices = []
    for filename in os.listdir(directory):
        if filename.endswith(".dcm"):
            filepath = os.path.join(directory, filename)
            ds = pydicom.dcmread(filepath)
            if 'InstanceNumber' in ds:
                slices.append(ds.InstanceNumber)
    return len(set(slices))

### Function to set a common FrameOfReferenceUID metadata for all instances of a serie
def set_frame_of_reference_UID(workingFolder):
  for dirpath, dirnames, filenames in os.walk(workingFolder):
    if filenames:
      frame_of_reference_uid = generate_uid()
      for dicom_file in os.listdir(dirpath):
        dicom_file_path = os.path.join(dirpath, dicom_file)
        if os.path.isfile(dicom_file_path) and dicom_file.endswith('.dcm'):
          dcm = pydicom.dcmread(dicom_file_path)
          dcm.FrameOfReferenceUID = frame_of_reference_uid
          dcm.save_as(dicom_file_path)

### Function to send a DICOM file to a distant PACS
def cStore_dataset(dicom_file_path, assoc):
  # Checking if dicom file is valid
  try:
    ds = dcmread(dicom_file_path)
  except Exception as e:
    print(f"Error reading the DICOM file {dicom_file_path} : {e}")
    return
  print("Association with ORTHANC : ", assoc.is_established)  
  if assoc.is_established:
    status = assoc.send_c_store(ds)

    # Checking operation status
    if status and status.Status == 0x0000:
      os.remove(dicom_file_path)
      return
    else:
      print(f"Sending the file {dicom_file_path} failed with status : {status.Status if status else 'Unknown'}")
    
  else:
    print("Unable to establish a connection with PACS.")
    # try:
    #   assoc = ae.associate(pacs_ip, pacs_port, ae_title=pacs_ae_title)
    # except Exception as e:
    #   print(f"Error establishing a connection with PACS : {e}")

def update_progress(progress, subject_id, dataset_id, progress_file):
    if subject_id not in progress:
        progress[subject_id] = []
    if dataset_id not in progress[subject_id]:
        progress[subject_id].append(dataset_id)
    with open(progress_file, 'w') as f:
      json.dump(progress, f, indent=2)

def connectToPacs():
  # Initialize PACS connexion
  ae = AE(ae_title=client_ae_title)

  # Add SOP class service for MR and X-Ray images
  ae.add_requested_context(MRImageStorage)
  ae.add_requested_context(XRayAngiographicImageStorage)

  ae.add_supported_context(MRImageStorage)
  ae.add_supported_context(XRayAngiographicImageStorage)

  ae.start_server(('127.0.0.1', listen_port), block=False)

  # Request an association with the PACS
  return ae.associate(pacs_ip, pacs_port, ae_title=pacs_ae_title)

if __name__ == '__main__':
  parser = create_arg_parser()
  add_common_arguments(parser)
  add_subjects_argument(parser)
  add_configuration_arguments(parser)
  args = parser.parse_args()

  config = api_service.initialize(args)

  # Request an association with the PACS
  #assoc = connectToPacs()

  getDatasets(config, args.subjects_csv, args.study) #assoc

  # Release the association with the PACS
  #assoc.release()
