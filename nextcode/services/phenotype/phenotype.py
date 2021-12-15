"""
Phenotype
------------------

Representation of a serverside phenotype.


"""

import json
import datetime
import dateutil
import time
import logging
from typing import Callable, Union, Optional, Dict, List
try:
    import pandas as pd
except ModuleNotFoundError:
    print('pandas is not installed - some functions might not work')
try:
    import plotly.graph_objects as go
    from plotly.offline import init_notebook_mode, iplot
except ModuleNotFoundError:
    print('plotly is not installed - some functions might not work')

from .exceptions import PhenotypeError
from .phenotype_matrix import PhenotypeMatrix
from ...exceptions import ServerError
from ...session import ServiceSession

log = logging.getLogger(__name__)

class Phenotype:
    """
    A local object representing a phenotype response from the phenotype
    catalog service.

    Note that most of the attributes come directly from the phenotype
    serverside response and are therefore not documented directly here.
    Please refer to the API Documentation for the phenotype catalog service.

    In addition to the ones documented here, this object has at least these attributes:

    * name - Phenotype name
    * description - Textual description of this phenotype
    * result_type - Type of result. Cannot be changed. One of SET, QT, CATEGORY
    * created_at - Timestamp when the phenotype was first created
    * updated_at - Timestamp when the phenotype was last updated
    * created_by - Username who created the phenotype
    * versions - List of data versions available in this phenotype

    To intraspect the data you can call `phenotype.data.keys()`. Each key
    in the `data` dict is exposed as an attribute with intelligent type casting.

    """

    def __init__(self, session: ServiceSession, data: Dict):
        self.session = session
        self.data = data
        self.links = data["links"]
        self.df = None

    def __getattr__(self, name):
        try:
            val = self.data[name]
        except KeyError:
            raise AttributeError

        try:
            val = dateutil.parser.parse(val)
        except Exception:
            pass

        return val

    def __repr__(self) -> str:
        return f"<Phenotype {self.name} in project {self.project_key}>"

    def refresh(self):
        """
        Refresh the local cache
        """
        resp = self.session.get(self.links["self"])
        data = resp.json()
        self.data = data["phenotype"]

    def delete(self):
        """
        Delete a phenotype, including all data from a project

        :raises: `ServerError` if the phenotype could not be deleted
        """
        _ = self.session.delete(self.links["self"])

    def upload(self, data: Union[List,pd.DataFrame]):
        """
        Upload phenotype data

        The data is expected to be either a list of lists or pandas DataFrame.
        e.g. `phenotype.upload([['a'], ['b']])`.
        The `result_type` of the phenotype dictates
        if each sublist should contain one or two items.

        :raises: `ServerError` if there was a problem uploading
        """
        if not isinstance(data, list):
            if isinstance(data, pd.DataFrame):
                data = data.values.tolist()
            else:
                raise TypeError("data must be a list or pandas DataFrame")

        url = self.links["upload"]

        content = {"data": data}
        resp = self.session.post(url, json=content)
        return resp.json()

    def update(self, description: Optional[str] = None, tags:  Optional[List[str]] = None, query: Optional[str] = None, category: Optional[str] = None, url: Optional[str] = None):
        """
        Update phenotype attributes
        """
        uri = self.links["self"]

        if tags and not isinstance(tags, list):
            tags = [tags]

        content = {"description": description,
                   "query": query,
                   "tag_list": tags,
                   "category": category,
                   "url": url
                   }

        self.session.patch(uri, json={k: v for k, v in content.items() if v is not None})
        self.refresh()

    def update_query(self, query: str):
        """
        Update the phenotype with a new query that defines this phenotype 
        """
        self.update(query = query)

    def update_description(self, description: str):
        """
        Update the phenotype with a new description
        """
        self.update(description = description)

    def set_tags(self, tags: List[str]):
        """
        Set the tag list for this phenotype, overriding all previous tags
        """
        self.update(tags = tags)

    def get_tags(self):
        """
        Retrieve all tags for this phenotype
        """
        return self.tag_list

    def add_tag(self, tag: str):
        """
        Add a new tag to this phenotype.

        :raises: `PhenotypeError` if the tag is already set on this phenotype
        """
        tags = set(self.tag_list)
        if tag in tags:
            raise PhenotypeError(f"Tag {tag} already exists on this phenotype")

        tags.add(tag)
        self.update(tags = list(tags))

    def delete_tag(self, tag: str):
        """
        Delete a tag from the phenotype.

        :raises: `PhenotypeError` if the tag does not exist
        """
        tags = set(self.tag_list)
        try:
            tags.remove(tag)
        except KeyError:
            raise PhenotypeError(f"Tag {tag} does not exist on this phenotype")

        self.update(tags = list(tags))
    
    def get_info(self):
        """
        Retrieve info for this phenotype
        """
        return self.data

    def get_data(self, label: Optional[str] = None):
        """
        Retrieve a phenotype data from the server.
        """
        matrix = PhenotypeMatrix(self.session, project_name = self.data["project_key"])
        matrix.add_phenotype(name = self.data["name"], label = label)
        self.df = matrix.get_data()
        return self.df

    def display(self, title=None):
        """
        Display phenotype

        :title: Phenotype plot title. Default: Phenotype name.
        """
        if not title:
            title = self.data['name']

        if self.df is None:
            self.get_data()
        
        switcher = {
            "SET": self._plot_set,
            "QT": self._plot_qt,
            "CATEGORY": self._plot_categorical
        }

        init_notebook_mode()

        layout = {
            'title': title,
            'hovermode': False, 
            'showlegend': False,
            'width': 500,
            'height': 400
        }

        fig = switcher.get(self.data.get("result_type"), "Nothing")(layout=layout)
        iplot(fig)

    def _plot_qt(self, **kwargs):
        """
        Plot QT phenotype
        """
        grp_col = self.df.columns[1]
        fig = go.Figure([go.Histogram(x=self.df[grp_col])],
                   **kwargs)
        fig.update_layout(yaxis={'title': "Count"})
        return fig

    def _plot_categorical(self, **kwargs):
        """
        Plot CATEGORICAL phenotype
        """
        grp_col = self.df.columns[1]
        grp_df = self.df.groupby(grp_col).count()
        grp_df = grp_df.reset_index()
 
        fig = go.Figure([go.Bar(x=[str(x) for x in grp_df[grp_col]], y = grp_df['pn'])],
                   **kwargs)
        fig.update_layout(xaxis={'title': "Category"},
                          yaxis={'title': "Count"})
        return fig

    def _plot_set(self, **kwargs):
        """
        Plot SET phenotype
        """
        fig = go.Figure([go.Pie(labels=["Count"], values=[len(self.df.index)])], **kwargs)
        fig.update_traces(textinfo='value')
        return fig
