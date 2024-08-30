import csv
from datetime import datetime

from py_noir.dataset.datasets_dataset_service import get_dataset
from py_noir.dataset.datasets_vip_execution_service import create_executions
from py_noir.security.shanoir_context import ShanoirContext

if __name__ == '__main__':

    context = ShanoirContext()
    context.domain = 'shanoir-ofsep-qualif.irisa.fr'
    context.username = 'ymerel'
    context.output_folder = 'output'

    with open("sample.tsv") as file:
        sample_file = csv.reader(file, delimiter="\t")

        isHeader = True

        examinations = dict()

        for line in sample_file:
            if isHeader:
                isHeader = False
                continue

            dataset = get_dataset(context, line[5])

            ds_id = dataset["id"]
            study_id = dataset["studyId"]
            exam_id = dataset["datasetAcquisition"]["examination"]["id"]
            if exam_id not in examinations:
                examinations[exam_id] = {}
                examinations[exam_id]["studyId"] = study_id
                examinations[exam_id]["T2"] = []
                examinations[exam_id]["STIR"] = []

            if "T2DSAGSTIR" in dataset["updatedMetadata"]["name"]:
                examinations[exam_id]["STIR"].append(ds_id)
            elif "T2DSAGT2" in dataset["updatedMetadata"]["name"]:
                examinations[exam_id]["T2"].append(ds_id)

        executions = []

        for key, value in examinations.items():
            for t2 in value["T2"]:
                execution = {
                    "name": "comete_moelle_01_exam_{}_{}".format(key, datetime.utcnow().strftime('%F_%H%M%S%f')[:-3]),
                    "pipelineIdentifier": "comete_moelle/0.1",
                    "inputParameters": {},
                    "datasetParameters": [
                        {
                            "name": "t2_archive",
                            "groupBy": "DATASET",
                            "exportFormat": "nii",
                            "datasetIds": [t2],
                            "converterId": 2
                        },
                        {
                            "name": "stir_archive",
                            "groupBy": "EXAMINATION",
                            "exportFormat": "nii",
                            "datasetIds": value["STIR"],
                            "converterId": 2
                        }
                    ],
                    "studyIdentifier": value["studyId"],
                    "outputProcessing": "",
                    "processingType": "SEGMENTATION",
                    "refreshToken": context.refresh_token,
                    "client": context.clientId,
                    "converterId": 6
                }
                executions.append(execution)

        create_executions(context, executions, True)

