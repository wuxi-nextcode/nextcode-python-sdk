Running a local workflow
========================

When creating workflows the developer will typically use the nextcode-cli to run the nextflow scripts against a remote server. On occasion though it can be beneficial to run the workflow by using the sdk.

An example of this is when the developer is using Jupyter notebooks and might not have direct access to the CLI interface for some reason.

The process is not overly complicated and here we will show you how to achieve this. This applies both to running python locally and through a Jupyter notebook. For simplicity we will assume you are doing this through Jupyter but the same principles apply however you are accessing the sdk.

Since the example assumes that you are running through Jupyter we do not need to install the sdk or set up user credentials.

To start off with, create a folder for your nextflow script. We assume a working knowledge of Nextflow in this tutorial. The folder can be called anything but we will name it `workflow-test`. Inside that folder we will need to create two files. `main.nf` and `nextflow.config`. This is the basic structure that is needed for nextflow.

The config file must contain a special `includeConfig` directive which allows it to work within a workflow. If you omit it you will get errors when running the workflow. Other than that you can include normal nextflow configuration. 

In this example we will run the `python` docker image for all of the processes which is very convenient since it contains most basic linux tools. In addition we will use the `echo` option so that the nextflow logs include all text that is emitted from the processes.

The `nextflow.config` file looks something like this.

.. code-block:: bash

  includeConfig '/work/base.config'
  process.container = 'python'
  process.echo = true

The `main.nf` file that we start off with is just a simple "hello world" script.

.. code-block:: bash

  process test {
      script:
      """
      echo Hello world
      """
  }

Now that we have these two files set up we can try to run this through the worklow service. To start off with we need to add AWS access to the scratch bucket that the SDK will use to upload your build. Typically this will be `nextcode-scratch` and we will assume so here.

**You will need to acquire the AWS access key for s3://nextcode-scratch to continue this tutorial.**

In jupyter notebook you can add the AWS keys using the following code:

.. code-block:: bash

  %env AWS_ACCESS_KEY_ID=********
  %env AWS_SECRET_ACCESS_KEY=********

.. hint:: In bash you would use `export AWS_ACCESS_KEY_ID=********` and `export AWS_SECRET_ACCESS_KEY=********` before running your python script instead, or just use the normal aws cli profile by `export AWS_PROFILE=<scratch-profile-name>`

You can now run the following code in order to execute the workflow:

.. code-block:: python

  import nextcode
  svc = nextcode.get_service("workflow")
  job = svc.run_local("workflow-test")
  job.wait()
  print(f"Job {job.job_id} is {job.status}")
  print(job.logs())

In this snippet we run the local workflow, wait for it to complete and then print out the logs, which should include your 'Hello world' message that is printed out by the nextflow process on the remote server.

This is a very basic overview and you can view the documentation for the workflow service to see how the service can be used fully. You can also view docstrings for individual methods from within jupyter (e.g. `svc.run_local.__doc__`).
