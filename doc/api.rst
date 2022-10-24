API Reference
-------------

These pages feature low-level documentation of the functionality of the SDK.

When using the SDK you always start by getting a `Client` instance using an API Key. With this object you can connect to various services.

.. code-block:: python
   :linenos:

   from nextcode import Nextcode
   nc = Nextcode(api_key="xxx", project="myproject")
   nc.phenoteke.map_cids_to_ipns(
      site_id='siteid',
      study_id='studyid',
      cids=['cid1', 'cid2', 'cid3']
   )
   nc.phenotype.create_phenotype('mypheno', 'myresulttype')
   nc.pipelines.get_jobs()
   nc.query.get_template('mytemplate')
   nc.queryserver.execute('gor ref/dbsnp.gorz | top 1')
   nc.workflow.post_job('mypipeline', 'myproject', params={})


Available Services
==================

.. toctree::
   :maxdepth: 2

   api_query
   api_workflow
   api_pipelines
   api_phenotype
   api_exceptions
   api_basic