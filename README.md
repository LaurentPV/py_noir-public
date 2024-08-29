PyNoir
===

PyNoir is a Python library aiming at facilitate the use of Shanoir APIs through Python scripts

# Repository structure
- `py_noir` directory contains the Shanoir API client methods
  - `dataset` directory contains dataset microservice API methods
  - `security` directory contains methods for managing authentication context
  - `api_service.py` declare generic methods for HTTP queries
- `projects` directory contains project specific scripts using PyNoir lib

# How to use PyNoir

First, declare and configure a `ShanoirContext` object

```python
from py_noir.security.shanoir_context import ShanoirContext
...
context = ShanoirContext()
context.domain = 'shanoir-ofsep-qualif.irisa.fr'
context.username = 'ymerel'
context.output_folder = 'output'
```

Then call the API method you need. The first argument is always the `ShanoirContext`.
```python
from py_noir.dataset.datasets_dataset_service import get_dataset
...
dataset = get_dataset(context, 1258)
```
When needed, authentication will be asked through console on runtime

```shell
$ python main.py
Password for Shanoir user ymerel:
```

Response object is a dictionary following JSON structure (see API doc for details)

```python
...
ds_id = dataset["id"]
exam_id = dataset["datasetAcquisition"]["examination"]["id"]
```


