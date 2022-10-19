from nextcode import Client


class Nextcode:
	def __init__(self, api_key=None, profile=None):
		self.client = Client(api_key=api_key, profile=profile)
		#self.pheno = self.client.service('phenotype')
		self.query = self.client.service('query')
		self.queryserver = self.client.service('queryserver')
		self.workflow = self.client.service('workflow')
