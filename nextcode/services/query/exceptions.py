"""
Exceptions
~~~~~~~~~~

Custom exceptions raised by the query service.

"""

from typing import List


class TemplateError(Exception):
    pass


class QueryError(Exception):
    def __init__(self, message: str, query_id: int = None):
        self.query_id = query_id


class MissingRelations(Exception):
    def __init__(self, relations: List):
        self.relations = relations

    def __repr__(self):
        return "MissingRelations: {}".format(", ".join(self.relations))
