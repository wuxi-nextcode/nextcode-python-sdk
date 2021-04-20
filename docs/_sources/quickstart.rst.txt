Quick Start
============

Once the sdk is installed you should be ready to connect to services. Please see the sections below for details.

Usage
-----
In order to use this SDK you will need to start by getting an **API KEY** from a Genuity Science server. These API Keys are JWT token that you must use to initialize the SDK.

You can then get started with the following:

.. code-block:: python

  import nextcode
  client = nextcode.Client(api_key="xxx")
  qry = client.service("query")
  qry.status()

This example allows you to verify that the API Key is correct and that the *query* service is responding. Please refer to the included documents for actual use cases.

API Key
-------
You will need an API Key for all actions in the nextcode sdk. If you have a local keycloak user (non-saml) you can get the key with the following code:

.. code-block:: python

  from nextcode.client import get_api_key
  api_key = get_api_key("www.myserver.com", "username", "password")

This will work for service users that have been added to keycloak by an administrator but if you are using your own account through OAuth you will need to log in via a webpage. The SDK has a helper method for this:

.. code-block:: python

  from nextcode.keycloak import auth_popup
  auth_popup("www.myserver.com")
  # This will pop up a browser window in which the user can login in and then gets presented with an auth token that can be copied

Alternatively you can navigate your brower directy to https://myserver.com/api-key-service

The API Key lifetime varies between keycloak installations but typically it is a month and the time will reset each time it is used. Therefore you should be able to save your api key locally for use in the sdk.

The SDK can cache the api key for you via **profiles**. To create a new profile you can use the following:

.. code-block:: python

  from nextcode.config import create_profile
  create_profile("myprofile", api_key)

After this your profile is saved into `~/.nextcode`.

Therefore, for a complete example you would do the following the first time you use the SDK using a service user:

.. code-block:: python

  import nextcode
  nextcode.keycloak.auth_popup("www.myserver.com")
  # ... retrieve the api key
  api_key = "..."
  config.create_profile("myprofile", api_key)
  nextcode.config.set_default_profile("myprofile")

Now you can start a new python session and use:

.. code-block:: python

  import nextcode
  svc = nextcode.get_service("query")
  svc.status()

This will use your saved API key from the previous session.

Also note that if you use the nextcode-cli this process is simplified.
