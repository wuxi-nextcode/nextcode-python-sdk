Developer information
-----------------------

If you are developing the nextcode-python-sdk you should start by cloning it from the github repository (or fork it).

.. code-block:: bash

  $ git clone git@github.com:wuxi-nextcode/nextcode-python-sdk.git

You can then use this version of the sdk in your system with the following command:

.. code-block:: bash

  $ pip install -e .

This will install the package in 'editable' mode and allow you to pull latest bleeding-edge versions.

Building and releasing
=======================

The SDK is built and deployed to Pypi in a Travis CI job. This job can be seen here: https://travis-ci.org/wuxi-nextcode/nextcode-python-sdk

A new release is made when a new version tag is added in git. Typically not every change is released, but it is relatively easy to make one.

First we typically bump the patch version (or minor or major)

.. code-block:: bash

  $ make bump

Then we run tests, linting and build documentation with *tox* (which you might need to install)

.. code-block:: bash

  $ tox

Now we check in the code along with all the documentation (all the html will be changed since the version string is on all the pages).

.. code-block:: bash

  $ git add .
  $ git commit -m "..."
  $ git push

When we are ready to release we merge the code into the *master* branch through a Pull Request.

Now we set the tag of *HEAD* on master to the version. This can be done through the commandline.

.. code-block:: bash

  $ make tag

Now Travis takes over and builds a new release which is automatically pushed to Pypi. You can follow the progress on the travis-ci page.

In a few minutes verify that your package is available here: https://pypi.org/project/nextcode-sdk/
