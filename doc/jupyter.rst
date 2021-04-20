Jupyter Notebooks Integration
-----------------------------

Genuity Science Python SDK can be used with Jupyter Notebooks and introduces `%gor` and `%%gor` magics.

If you are running a session in one of Wuxi Nextcode's own notebook servers no installation should be required and you can skip to the next section.

Installation
=============

However, if you are running your own jupyter server you can install the python sdk in your workspace.

.. code-block:: bash

    pip install nextcode-sdk[jupyter]

Then you intialize the extension in your notebook after you have received an API key for the server. You will also need a project name that your user account has access to.

.. code-block:: python

    %env GOR_API_KEY=****
    %env GOR_API_PROJECT=****
    %load_ext nextcode

    Gor magic extension has been loaded. You can now use '%gor' and '%%gor' in this notebook
    * Python SDK Version: 0.1.6
    * Query API Version: 1.9.0
    * GOR Version: 9.4-SNAPSHOT (git SHA 8fc327bb08282d02f9e987e11c4073e64ec77677)
    * Root Endpoint: <endpoint>
    * Current User: testuser


Getting Started
===============

Now magic syntax should be available. Try it out:

.. code-block:: python

    %gor gor #dbsnp# | top 2
    Chrom   pos reference   allele  rsids
    0   chr1    10020   AA  A   rs775809821
    1   chr1    10039   A   C   rs978760828

The magic commands return a pandas dataframe object which by default prints out to console and is available through `_`. You can also assign it directly to a variable

.. code-block:: python

    var = %gor gor #dbsnp# | top 2
    var
    Chrom   pos reference   allele  rsids
    0   chr1    10020   AA  A   rs775809821
    1   chr1    10039   A   C   rs978760828

... etc.

Please see the included Example Jupyter Notebook page for more examples.