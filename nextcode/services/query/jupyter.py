"""
Jupyter Extensions
------------------

Bootstrapping for Jupyter Notebook magic syntax, `%gor` and `%%gor`
"""

from ...exceptions import ServerError, InvalidToken
from .exceptions import MissingRelations, QueryError
from typing import Dict, List, Optional, Union
import nextcode
import hashlib
import time
import logging
import re
import sys
import os

log = logging.getLogger(__name__)

try:
    import pandas as pd
    from IPython.core.magic import Magics, magics_class, line_magic, line_cell_magic

    jupyter_available = True
except ImportError:
    jupyter_available = False
    Magics = object
    line_cell_magic = None

    def magics_class(cls):
        return cls

    def line_cell_magic(func):
        return func

    def line_magic(func):
        return func


def print_details(txt):
    if os.environ.get("LOG_QUERY"):
        print(txt)
        sys.stdout.flush()


def print_error(txt):
    print(txt, file=sys.stderr)
    sys.stderr.flush()


def sizeof_fmt(num, suffix="B"):
    import math

    if not num:
        return "-"
    magnitude = int(math.floor(math.log(num, 1024)))
    val = num / math.pow(1024, magnitude)
    if magnitude > 7:
        return "{:.1f}{}{}".format(val, "Yi", suffix)
    return "{:3.1f}{}{}".format(
        val, ["", "Ki", "Mi", "Gi", "Ti", "Pi", "Ei", "Zi"][magnitude], suffix
    )


def get_service():
    svc = nextcode.get_service("query")
    return svc


@magics_class
class GorMagics(Magics):
    def handle_exception(self):
        exception = sys.exc_info()
        print_error(str(exception[1]))

    def replace_vars(self, string):
        replacement_vars = re.findall("\\$([a-zA-Z0-9_]+)?", string)
        ret = string
        user_ns = self.shell.user_ns
        for var_name in replacement_vars:
            if var_name not in user_ns.keys():
                raise Exception("Variable '%s' not found" % var_name) from None
            var = str(user_ns[var_name])
            ret = ret.replace(f"${var_name}", var)
        return ret

    def load_relations(self, relation_names):
        relations = []
        user_ns = self.shell.user_ns
        print_details(
            "Loading relations {} from local state".format(", ".join(relation_names))
        )
        for name in relation_names:
            var_name = name.replace("[", "").replace("]", "").split(":")[-1]
            if var_name not in user_ns.keys():
                raise Exception("Variable '%s' not found" % var_name) from None
            var = user_ns[var_name]
            if not isinstance(var, pd.DataFrame):
                raise Exception(
                    "%s must be a pandas DataFrame object, not %s"
                    % (var_name, type(var))
                ) from None
            md5 = hashlib.md5()
            md5.update(str(id(user_ns[var_name])).encode())
            data = var.to_csv(index=False, sep="\t")
            relations.append(
                {
                    "name": name,
                    "fingerprint": md5.hexdigest(),
                    "extension": ".tsv",
                    "data": data,
                }
            )
        return relations

    @line_cell_magic
    def gor(self, line, cell=None):
        try:
            st = time.time()
            svc = get_service()
            gor_string = line
            return_var = None
            persist = None
            user_ns = self.shell.user_ns
            qry = None
            # if this is a multiline statement
            if cell:
                # if there is a << on the first line we assume we have an assignment or a persist
                if "<<" in line:
                    parts = line.split("<<")
                    var = parts[0].strip()
                    # if the variable looks like it might be a filename, persist it, otherwise assign to a local var
                    if "/" in var or "." in var:
                        persist = var
                    else:
                        return_var = var
                    gor_string = parts[1]
                gor_string += "\n" + cell

            gor_string = self.replace_vars(gor_string)
            try:
                qry = svc.execute(gor_string, nowait=True, persist=persist)
            except MissingRelations as ex:
                relations = self.load_relations(ex.relations)
                qry = svc.execute(
                    gor_string, relations=relations, nowait=True, persist=persist
                )
            start_time = time.time()
            while qry.running is True:
                try:
                    qry.wait(max_seconds=10)
                except QueryError as ex:
                    if qry.running:
                        print_details(
                            f"Query {qry.query_id} has status {qry.status} after {(time.time()-start_time):.0f} seconds"
                        )
                    else:
                        raise

            if qry.status != "DONE":
                try:
                    print_error(
                        "Query {} failed with error:\n{}".format(
                            qry.query_id, qry.status_message
                        )
                    )
                except TypeError:
                    raise Exception(
                        "Query {} has unexpected status {}".format(
                            qry.query_id, qry.status
                        )
                    )
                return None
            num_rows = qry.line_count or 0
            print_details(
                "Query {} returned {} rows in {:.2f} sec".format(
                    qry.query_id, num_rows, time.time() - st
                )
            )
            if persist:
                return None
            MAX_ROWS = 1000000
            if num_rows > MAX_ROWS:
                print_error(
                    "Query {} returned {} rows but magic commands are capped at {} rows.".format(
                        qry.query_id, qry.line_count, MAX_ROWS
                    )
                )
            ret = qry.dataframe(limit=MAX_ROWS)
            if return_var:
                user_ns[return_var] = ret
                return None
            else:
                return ret
        except KeyboardInterrupt:
            if qry:
                try:
                    qry.cancel()
                except QueryError:
                    pass
            print_error("Query has been cancelled")
            return None
        except Exception:
            self.handle_exception()

    @line_magic
    def gorls(self, line):
        """
        Just a fun little experiment
        """
        svc = get_service()
        parts = line.replace("  ", " ").split(" ")
        path = parts[0]
        grep = None
        if len(parts) >= 2:
            grep = parts[1]
        gor_string = (
            f"""nor {path} | SELECT Filename,isDir,FileSize | SORT -c fileName"""
        )
        if grep:
            gor_string += f" | GREP {grep}"
        qry = svc.execute(gor_string)
        results = qry.get_results()

        ret = []
        for row in results["data"]:
            txt = row[0]
            if row[1] == "true":
                txt += "/"
            else:
                txt += " ({sz})".format(sz=sizeof_fmt(int(row[2])))
            ret.append(txt)
        print("\n".join(ret))
        return None

    @line_magic
    def gorfind(self, line):
        """
        Just a fun little experiment
        """
        svc = get_service()
        string = line
        # okay, you crazy fool. Now we run a bunch of queries to crawl through the entire directory
        # structure of the project to find all folders. Then we run a nor command on each of these
        # folders to grep for the string
        gor_string = f"""nor . -r -d 3 | SELECT Filepath | GREP {string}"""
        qry = svc.execute(gor_string)
        results = qry.get_results()
        folders = results["data"]
        ret = []
        for f in folders:
            ff = f[0].split(svc.project)[-1]
            ret.append(ff)
            print(ff)


# In order to actually use these magics, you must register them with a
# running IPython.
def load_ipython_extension(ipython):
    """
    Any module file that define a function named `load_ipython_extension`
    can be loaded via `%load_ext module.path` or be configured to be
    autoloaded by IPython at startup time.
    """
    # You can register the class itself without instantiating it.  IPython will
    # call the default constructor on it.
    ipython.register_magics(GorMagics)

    try:
        svc = get_service()
    except InvalidToken:
        print_error("Invalid GOR_API_KEY")
        return
    except ServerError as ex:
        print_error(str(ex))
        return
    status = svc.status(force=True)
    print(
        " Gor magic extension has been loaded. You can now use '%gor' and '%%gor' in this notebook"
    )
    print(" * Python SDK Version: {}".format(nextcode.__version__))
    print(" * Query API Version: {}".format(status["build_info"]["version"]))
    print(" * GOR Version: {}".format(status["build_info"]["gor_services_version"]))
    print(" * Root Endpoint: {}".format(status["root"]))
    print(" * Current User: {}".format(svc.current_user["email"]))


class QueryBuilder:

    defs: Dict[str, str] = {}
    creates: Dict[str, str] = {}

    def __init__(self):
        self.defs = {}
        self.creates = {}

    def render(self, stmt):
        string = ""
        for k, v in self.defs.items():
            v = str(v)
            if not v.endswith(";"):
                v += ";"
            string += "def {} = {}\n".format(k, v)
        string += "\n"
        for k, v in self.creates.items():
            if not v.endswith(";"):
                v += ";"
            string += "create [{}] = {}\n".format(k, v)
        string += "\n"

        string += stmt
        return string

    def execute(self, stmt, **kw):
        svc = nextcode.get_service("query")
        query = self.render(stmt)
        return svc.execute(query, **kw)
