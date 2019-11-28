Nextcode Python SDK
===================

What is it?
-----------
Nextcode-sdk is a python package for interfacing with WuXi Nextcode RESTFul services.

.. note::

    These services are not publicly accessible and only available within private installations. Therefore you will not be able to use this SDK unless you work for, or are a client of WuXi Nextcode.
    
    Please contact `WuXi Nextcode
    <https://www.WuXinextcode.com/>`_ for additional information.

Installation
-------------

To install this package you can can either install the raw sdk or include the jupyter dependencies if you intend to
run this through jupyter notebooks.

.. code-block:: bash

   pip install nextcode-sdk -U
   pip install nextcode-sdk[jupyter] -U

Note that this package supports Python version **3.6** and higher only.

Usage
-----
In order to use this SDK you will need to start by getting an **API KEY** from a WuXi Nextcode server. These API Keys are JWT token that you must use to initialize the SDK.

You can then get started with the following:

.. code-block:: python

  import nextcode
  client = nextcode.Client(api_key="xxx")
  qry = client.service("query")
  qry.status()

This example allows you to verify that the API Key is correct and that the *query* service is responding. Please refer to the included documents for actual use cases.

Contents
--------

.. toctree::
   :maxdepth: 3

   jupyter
   api
   notebook
   apidoc
   development

Indices and tables
-------------------

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`


Resources
---------

`WuXi Nextcode website <https://wuxinextcode.com>`_, Keep up to date on WuXi Nextcode

`IPython website <https://ipython.org>`_, Learn more about IPython

`Nextcode Python SDK Github page <https://github.com/wuxi-nextcode/nextcode-python-sdk>`_, Download the source code to the SDK.

