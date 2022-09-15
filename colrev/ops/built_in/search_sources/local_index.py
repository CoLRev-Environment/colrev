#! /usr/bin/env python
import typing
from pathlib import Path

import pandas as pd
import pandasql as ps
import zope.interface
from dacite import from_dict
from pandasql.sqldf import PandaSQLException
from tqdm import tqdm

import colrev.env.package_manager
import colrev.exceptions as colrev_exceptions
import colrev.ops.built_in.database_connectors
import colrev.ops.search
import colrev.record

# pylint: disable=unused-argument
# pylint: disable=duplicate-code


@zope.interface.implementer(colrev.env.package_manager.SearchSourcePackageInterface)
class LocalIndexSearchSource:
    """Performs a search in the LocalIndex"""

    settings_class = colrev.env.package_manager.DefaultSourceSettings
    # TODO : add a colrev_projet_origin field and use it as the identifier?
    source_identifier = "index"
    source_identifier_search = "index"
    search_mode = "individual"

    def __init__(self, *, source_operation, settings: dict) -> None:
        if "selection_clause" not in settings["search_parameters"]:
            raise colrev_exceptions.InvalidQueryException(
                "selection_clause required in search_parameters"
            )
        self.settings = from_dict(data_class=self.settings_class, data=settings)

    def run_search(self, search_operation: colrev.ops.search.Search) -> None:
        params = self.settings.search_parameters
        feed_file = self.settings.filename

        records: list = []
        imported_ids = []
        if feed_file.is_file():
            with open(feed_file, encoding="utf8") as bibtex_file:
                feed_rd = search_operation.review_manager.dataset.load_records_dict(
                    load_str=bibtex_file.read()
                )
                records = list(feed_rd.values())

            imported_ids = [x["ID"] for x in records]

        local_index = search_operation.review_manager.get_local_index()

        def retrieve_from_index(params) -> typing.List[dict]:

            # Note: we retrieve colrev_ids and full records afterwards
            # because the os.sql.query throws errors when selecting
            # complex fields like lists of alsoKnownAs fields

            query = (
                f"SELECT colrev_id FROM {local_index.RECORD_INDEX} "
                f"WHERE {params['selection_clause']}"
            )
            # TODO : update to opensearch standard (DSL?)
            # or use opensearch-sql plugin
            # https://github.com/opensearch-project/opensearch-py/issues/98
            # client.transport.perform_request
            #  ('POST', '/_plugins/_sql', body={'query': sql_str})
            # https://opensearch.org/docs/latest/search-plugins/sql/index/
            # see extract_references.py (methods repo)
            # resp = local_index.open_search.sql.query(body={"query": query})

            print("WARNING: not yet fully implemented.")
            quick_fix_query = (
                params["selection_clause"]
                .replace("title", "")
                .replace("'", "")
                .replace("%", "")
                .replace("like", "")
                .lstrip()
                .rstrip()
            )
            print(f"Working with quick-fix query: {quick_fix_query}")
            # input(query.replace(''))
            # resp = local_index.open_search.search(index=local_index.RECORD_INDEX,
            # body={"query":{"match_all":{}}})

            print("search currently restricted to title field")
            selected_fields = []
            if "title" in params["selection_clause"]:
                selected_fields.append("title")
            if "author" in params["selection_clause"]:
                selected_fields.append("author")
            if "fulltext" in params["selection_clause"]:
                selected_fields.append("fulltext")
            if "abstract" in params["selection_clause"]:
                selected_fields.append("abstract")

            # TODO : size is set to maximum.
            # We may iterate (using the from=... parameter)
            # pylint: disable=unexpected-keyword-arg
            # Note : search(...) accepts the size keyword (tested & works)
            # https://opensearch-project.github.io/opensearch-py/
            # api-ref/client.html#opensearchpy.OpenSearch.search
            resp = local_index.open_search.search(
                index=local_index.RECORD_INDEX,
                size=10000,
                body={
                    "query": {
                        "simple_query_string": {
                            "query": quick_fix_query,
                            "fields": selected_fields,
                        },
                    }
                },
            )

            # TODO : extract the following into a convenience function of search
            # (maybe even run in parallel/based on whole list and
            # select based on ?colrev_ids?)

            records_to_import = []
            for hit in tqdm(resp["hits"]["hits"]):
                record = hit["_source"]
                if "fulltext" in record:
                    del record["fulltext"]

                # pylint: disable=possibly-unused-variable
                rec_df = pd.DataFrame.from_records([record])
                try:
                    query = f"SELECT * FROM rec_df WHERE {params['selection_clause']}"
                    res = ps.sqldf(query, locals())
                except PandaSQLException:
                    continue
                if len(res) > 0:
                    records_to_import.append(record)

            # IDs_to_retrieve = [item for sublist in resp["rows"] for item in sublist]

            # records_to_import = []
            # for ID_to_retrieve in IDs_to_retrieve:

            #     hash = hashlib.sha256(ID_to_retrieve.encode("utf-8")).hexdigest()
            #     res = local_index.open_search.get(index=local_index.RECORD_INDEX, id=hash)
            #     record_to_import = res["_source"]
            #     record_to_import = {k: str(v) for k, v in record_to_import.items()}
            #     record_to_import = {
            #         k: v for k, v in record_to_import.items() if "None" != v
            #     }
            #     record_to_import = local_index.prep_record_for_return(
            #         record=record_to_import, include_file=False
            #     )

            #     if "" == params['selection_clause']:
            #         records_to_import.append(record_to_import)
            #     else:
            #         rec_df = pd.DataFrame.from_records([record_to_import])
            #         query = f"SELECT * FROM rec_df WHERE {params['selection_clause']}"
            #         res = ps.sqldf(query, locals())
            #         input(res)
            #         # if res...: append
            #         records_to_import.append(record_to_import)

            return records_to_import

        records_to_import = retrieve_from_index(params)

        records_to_import = [r for r in records_to_import if r]
        records_to_import = [
            x for x in records_to_import if x["ID"] not in imported_ids
        ]
        records = records + records_to_import

        keys_to_drop = [
            "colrev_status",
            "colrev_origin",
            "screening_criteria",
        ]
        records = [
            {key: item[key] for key in item.keys() if key not in keys_to_drop}
            for item in records
        ]

        if len(records) > 0:
            records_dict = {r["ID"]: r for r in records}
            search_operation.save_feed_file(records=records_dict, feed_file=feed_file)

        else:
            print("No records found")

    @classmethod
    def heuristic(cls, filename: Path, data: str) -> dict:
        # TODO
        result = {"confidence": 0, "source_identifier": cls.source_identifier}

        return result

    def load_fixes(self, load_operation, source, records):

        return records

    def prepare(self, record: colrev.record.Record) -> colrev.record.Record:

        return record


if __name__ == "__main__":
    pass
