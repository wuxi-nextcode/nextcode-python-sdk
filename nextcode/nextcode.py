from nextcode import Client


class Nextcode:
	def __init__(self, api_key=None, profile=None, project=None):
		self.client = Client(api_key=api_key, profile=profile)
		self.phenoteke = self.client.service('phenoteke')
		self.phenotype = self.client.service('phenotype', project=project)
		self.pipelines = self.client.service('pipelines')
		self.query = self.client.service('query')
		self.queryserver = self.client.service(
			'queryserver',
			project=project
		)
		self.workflow = self.client.service('workflow')
