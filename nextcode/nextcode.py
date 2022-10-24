"""
Nextcode
~~~~~~~~~~

This is the basic entrypoint to interact with services.
"""

from nextcode import Client


class Nextcode:
    """
    The main class used to interface with our APIs

    :param api_key: api key to use for this client
    :param profile: name of a saved profile to use with this client
    :param root_url: override the URL of the server root. e.g. https://server.wuxinextcode.com
    :raises: InvalidProfile

    Example usage:

    >>> from nextcode import Nextcode
    >>> nc = Nextcode(api_key="xxx")
    >>> nc.workflow.healthy()
    True
    """
    def __init__(self, api_key=None, profile=None, project=None, root_url=None):
        self.client = Client(api_key=api_key, profile=profile, root_url=root_url)
        self.phenoteke = self.client.service('phenoteke')
        self.phenotype = self.client.service('phenotype', project=project)
        self.pipelines = self.client.service('pipelines')
        self.query = self.client.service('query')
        self.queryserver = self.client.service(
            'queryserver',
            project=project
        )
        self.workflow = self.client.service('workflow')
