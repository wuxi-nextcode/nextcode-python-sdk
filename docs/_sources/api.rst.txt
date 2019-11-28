API Reference
-------------

These pages feature low-level documentation of the functionality of the SDK.

When using the SDK you always start by getting a `Client` instance using an API Key. With this object you can connect to various services.

.. code-block:: python
   :linenos:

   import nextcode
   client = nextcode.Client(api_key="xxx")
   svc = client.service("query")
   svc.status()

There is a helper method available to get a service directly without first invoking a client.

.. code-block:: python
   :linenos:

   import nextcode
   svc = nextcode.get_service("query")

In this example we assume the `api_key` has already been set but it can also be passed in.


Available Services
==================

.. toctree::
   :maxdepth: 2

   api_query
   api_workflow
   api_pipelines
   api_exceptions
   api_basic