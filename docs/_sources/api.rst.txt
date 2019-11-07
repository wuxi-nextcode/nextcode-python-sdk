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

.. automodule:: nextcode.client
   :members:

.. automodule:: nextcode.session
   :members:

.. automodule:: nextcode.config
   :members:

.. automodule:: nextcode.utils
   :members:

Available Services
==================

.. toctree::
   :maxdepth: 2

   api_query
   api_workflow
   api_exceptions