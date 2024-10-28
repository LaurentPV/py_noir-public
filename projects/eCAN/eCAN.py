from rich.progress import track
import click
import pydicom
from pydicom.uid import generate_uid
import os
from tqdm.notebook import tqdm
import pandas as pd
import py_noir.dataset.datasets_dataset_service as dds
import py_noir.studies.studies_subject_service as sss
from py_noir.security.shanoir_context import ShanoirContext

@click.command()
@click.option('--input', '-i', help='Input file path')
@click.option('--slice_thickness', default=0.5, help='Maximum slice thickness value (in mm), if not specified, default value is 0.5')
@click.option('--number_of_slices', default=50, help='Minimum number of slices value, if not specified, default value is 50')
@click.option('--study', default='UCAN', help='Clinical study from which we want to extract the data, if not specified, default value is UCAN')
@click.option('--username', prompt='Enter your Shanoir username', help='The Shanoir username to use')
#@click.option('--password', prompt='Enter your Shanoir password', help='The Shanoir password to use')
def main(input, slice_thickness, number_of_slices, study, username, password):

  context = ShanoirContext()
  context.domain = 'shanoir.irisa.fr'
  context.username = username

  # List of MRI types to consider
  mri_types = ["tof","angio","flight","mra", "arm"]
  results = []

  if study == 'UCAN':
    study_id = '178'
  elif study == 'ICAN':
    study_id = '124'

  # If "input" parameter is specified, we read the file and get the list of subject ids
  if input:
    df = pd.read_csv(input, header=None)
    subject_ids = df[0].unique().tolist()
  # If "input" parameter is not specified, we get the list of subject ids from the study id
  else:
    subject_ids = sss.find_subject_ids_by_study_id(context, study_id)
    df = pd.DataFrame(subject_ids)

  # For each patient (= subject in Shanoir) we get all datasets ids associated with the patient
  for subject_id in track(subject_ids, description="Processing Shanoir datasets..."):
    all_dataset_ids = dds.find_dataset_ids_by_subject_id_study_id(context, subject_id, study_id)
    for dataset in all_dataset_ids :
      is_tof = False
      enough_frames = False
      thin_enough = False
      # get dicom metadata for each dataset and check quality compliance
      dicom_metadata = dds.getDicomMetadataByDatasetId(dataset)
      if dicom_metadata is not None :
        for item in dicom_metadata:
          # Check if ProtocolName or SeriesDescription contains "tof" or "angio" or "flight"
          if ('0008103E' in item and any(x in item['0008103E']["Value"][0].lower() for x in mri_types)) or ('00181030' in item and any(x in item['00181030']["Value"][0].lower() for x in mri_types)):
            is_tof = True
          # Check if sliceThickness is OK
          if "00180050" in item and item["00180050"]["Value"] != [] and float(item["00180050"]["Value"][0]) < slice_thickness:
            thin_enough = True
          # Check if NumberOfSlices or NumberOfFrames or DataElements is OK -- KO ! a revoir
          if ("20011018" in item and item["20011018"]["Value"] != [] and int(item["20011018"]["Value"][0]) > number_of_slices) or ("00280008" in item and item["00280008"]["Value"] != [] and int(item["00280008"]["Value"][0]) > number_of_slices) or ("07A11002" in item and item["07A11002"]["Value"] != [] and int(item["07A11002"]["Value"][0]) > number_of_slices):
            enough_frames = True

        if is_tof and thin_enough and enough_frames :
          results.append(dataset)
    
  if results:
    print(f"Found {len(results)} datasets matching the criterias")

    dds.download_datasets(context, results, 'dcm', context.output_folder)

  # Correction of Frame of Reference UID value for each DICOM serie
  for dirpath, dirnames, filenames in track(os.walk(context.output_folder), description="Setting frame of reference UID for each DICOM serie..."):
    if filenames:
      print(f"Processing DICOM series in directory: {dirpath}")
      frame_of_reference_uid = generate_uid()
      for dicom_file in os.listdir(dirpath):
        dicom_file_path = os.path.join(dirpath, dicom_file)
        if os.path.isfile(dicom_file_path) and dicom_file.endswith('.dcm'):
          dcm = pydicom.dcmread(dicom_file_path)
          dcm.FrameOfReferenceUID = frame_of_reference_uid
          dcm.save_as(dicom_file_path)
          print(f"Updated FrameOfReferenceUID for {dicom_file_path}")

if __name__ == '__main__':
  main()


### Code de correction GE pour Frame of Refernce UID (0020,0052): 

# WrongFrameOfRef = False
#  for i in range(0, len(ipp)):
#    filename_dcm = dicom_infos_list[0]['Filename'][i]
#    dcm = pydicom.dcmread(filename_dcm)
#    if i == 0:
#      frameOfRef = dcm.FrameOfReferenceUID
#    if (frameOfRef != dcm.FrameOfReferenceUID):
#       WrongFrameOfRef = True
 

# if (WrongFrameOfRef):
#   print('Need to change frame of ref')
#   for i in range(0, len(ipp)):
#     filename_dcm = dicom_infos_list[0]['Filename'][i]
#     dcm = pydicom.dcmread(filename_dcm)
#     output_file = os.path.join(output, name, os.path.basename(filename_dcm))
#     if i == 0:
#       frameOfRef = dcm.FrameOfReferenceUID
#     dcm.FrameOfReferenceUID = frameOfRef
#     pydicom.dcmwrite(output_file, dcm)


### Fonction pour déduire le nombre d'images d'un dicom 

# def count_slices(directory):
#     slices = []
#     for filename in os.listdir(directory):
#         if filename.endswith(".dcm"):
#             filepath = os.path.join(directory, filename)
#             ds = pydicom.dcmread(filepath)
#             if 'InstanceNumber' in ds:
#                 slices.append(ds.InstanceNumber)
#     return len(set(slices))

# dicom_directory = "/path/to/dicom/files"
# num_slices = count_slices(dicom_directory)
# print(f"Number of slices: {num_slices}")