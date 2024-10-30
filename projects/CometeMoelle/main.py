import sys
sys.path.append( '../../')
sys.path.append( '../../py_noir/dataset')
import json

from datetime import datetime

from py_noir.dataset.datasets_dataset_service import find_dataset_ids_by_examination_id
from py_noir.dataset.datasets_vip_execution_service import create_executions
from py_noir.security.shanoir_context import ShanoirContext

if __name__ == '__main__':

    context = ShanoirContext()
    context.domain = 'shanoir-ofsep.irisa.fr'
    context.username = 'jcdouteau'
    context.output_folder = 'output'

    f = open("COMETE-M_exams_baseline.txt", "r")
    done = f.read()
    todo = done.split(",")
    isHeader = True

    examinations = dict()

    for exam_id_to_get in todo:
        datasets = find_dataset_ids_by_examination_id(context, exam_id_to_get)

        for dataset in datasets:
            ds_id = dataset["id"]
            study_id = dataset["studyId"]
            if exam_id_to_get not in examinations:
                examinations[exam_id_to_get] = {}
                examinations[exam_id_to_get]["studyId"] = study_id
                examinations[exam_id_to_get]["T2"] = []
                examinations[exam_id_to_get]["STIR"] = []

            if "T2DSAGSTIR" == dataset["updatedMetadata"]["name"]:
                examinations[exam_id_to_get]["STIR"].append(ds_id)
            elif "T2DSAGT2" == dataset["updatedMetadata"]["name"]:
                examinations[exam_id_to_get]["T2"].append(ds_id)

    executions = []

    identifier = 0
    for key, value in examinations.items():
        for t2 in value["T2"]:
            execution = {
                "name": "comete_moelle_01_exam_{}_{}".format(key, datetime.utcnow().strftime('%F_%H%M%S%f')[:-3]),
                "pipelineIdentifier": "comete_moelle/0.1",
                "inputParameters": {},
                "identifier": identifier,
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
            identifier = identifier + 1

    execFile = open("executions.json", "a")
    execFile.write(json.dumps(executions))
    execFile.close()
    create_executions(context, executions, True)

