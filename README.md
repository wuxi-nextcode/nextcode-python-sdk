[![Latest version on
PyPi](https://badge.fury.io/py/nextcode-sdk.svg)](https://badge.fury.io/py/nextcode-sdk)
[![Build Status](https://api.travis-ci.org/wuxi-nextcode/nextcode-python-sdk.svg?branch=master)](https://travis-ci.org/wuxi-nextcode/nextcode-python-sdk)
[![codecov](https://codecov.io/gh/wuxi-nextcode/nextcode-python-sdk/branch/master/graph/badge.svg)](https://codecov.io/gh/wuxi-nextcode/nextcode-python-sdk/branch/master)
[![Supported Python
versions](https://img.shields.io/pypi/pyversions/nextcode-sdk.svg)](https://pypi.org/project/nextcode-sdk/)
[![Code style:
black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
# nextcode Python SDK

Nextcode-sdk is a python package for interfacing with Wuxi Nextcode services.

### Installation
```bash
$ pip install nextcode-sdk -U
```

```bash
$ pip install nextcode-sdk[jupyter] -U
```

### Getting started

```python
import nextcode
client = nextcode.Client(api_key="xxx")
qry = client.service("query")
qry.status()
qry.get_queries()
qry.get_query(query_id)
qry.list_templates()

```

### Jupyter notebooks

To start using the python sdk in Jupyter Notebooks you will first need to install it using the `jupyter` extras and then load the gor `%` magic extension.

```bash
! pip install nextcode-sdk[jupyter] -U
%load_ext nextcode
```

Jupyter notebooks running on the Wuxi Nextcode servers are preconfigured with a `GOR_API_KEY` and `GOR_PROJECT`. If you are running outside such an environment you will need to configure your environment accordingly:
```bash
%env GOR_API_KEY="***"
%env GOR_API_PROJECT="test_project"
# optionally set the LOG_QUERY environment variable to get more information about running queries.
%env LOG_QUERY=1
```

Now you can run gor with the following syntax:
```python
# simple one-liner
%gor gor #dbsnp# | top 100

# one-liner which outputs to local variable as a pandas dataframe
results = %gor gor #dbsnp# | top 100

# multi-line statement
%%gor 
gor #dbsnp# 
  | top 100

# multi-line statement which writes results into project folder
%%gor user_data/results.tsv <<
nor #dbsnp# 
  | top 100

# output results to local variable as a pandas dataframe
%%gor myvar <<
nor #dbsnp# 
  | top 100

# read from a pandas dataframe in a local variable
%%gor
nor [var:myvar] 
  | top 100

# reference a local variable
num = 10
%%gor
nor [var:myvar] 
  | top $num

```
