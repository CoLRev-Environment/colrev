#! /usr/bin/env python
"""Connector to doi.org (API)"""
from __future__ import annotations

import html
import re
import time
from random import randint
from typing import TYPE_CHECKING

import colrev.record

if TYPE_CHECKING:
    import colrev.ops.prep


def json_to_record(*, item: dict) -> dict:
    """Convert a crossref item to a record dict"""

    # pylint: disable=too-many-branches
    # pylint: disable=too-many-statements
    # pylint: disable=too-many-locals

    # Note: the format differst between crossref and doi.org
    record_dict: dict = {}

    # Note : better use the doi-link resolution
    if "link" in item:
        fulltext_link_l = [u["URL"] for u in item["link"] if "pdf" in u["content-type"]]
        if len(fulltext_link_l) == 1:
            record_dict["fulltext"] = fulltext_link_l.pop()
    #     item["link"] = [u for u in item["link"] if "pdf" not in u["content-type"]]
    #     if len(item["link"]) >= 1:
    #         link = item["link"][0]["URL"]
    #         if link != record_dict.get("fulltext", ""):
    #             record_dict["link"] = link

    if "title" in item:
        retrieved_title = ""
        if isinstance(item["title"], list):
            if len(item["title"]) > 0:
                retrieved_title = str(item["title"][0])
        elif isinstance(item["title"], str):
            retrieved_title = item["title"]

        if retrieved_title:
            retrieved_title = retrieved_title.replace("\n", " ")
            retrieved_title = retrieved_title.replace("<scp>", "{")
            retrieved_title = retrieved_title.replace("</scp>", "}")
            retrieved_title = re.sub(r"<\/?[^>]*>", " ", retrieved_title)
            retrieved_title = re.sub(r"\s+", " ", retrieved_title)
            record_dict.update(title=retrieved_title)

    container_title = ""
    if "container-title" in item:
        if isinstance(item["container-title"], list):
            if len(item["container-title"]) > 0:
                container_title = item["container-title"][0]
        elif isinstance(item["container-title"], str):
            container_title = item["container-title"]

    container_title = container_title.replace("\n", " ")
    container_title = re.sub(r"\s+", " ", container_title)
    if "type" in item:
        if "journal-article" == item.get("type", "NA"):
            record_dict.update(ENTRYTYPE="article")
            if container_title is not None:
                record_dict.update(journal=container_title)
        if "proceedings-article" == item.get("type", "NA"):
            record_dict.update(ENTRYTYPE="inproceedings")
            if container_title is not None:
                record_dict.update(booktitle=container_title)
        if "book" == item.get("type", "NA"):
            record_dict.update(ENTRYTYPE="book")
            if container_title is not None:
                record_dict.update(series=container_title)

    if "DOI" in item:
        record_dict.update(doi=item["DOI"].upper())

    authors_strings = []
    for author in item.get("author", "NA"):
        a_string = ""

        if "family" in author:
            a_string += author["family"]
            if "given" in author:
                a_string += f", {author['given']}"
            authors_strings.append(a_string)
    authors_string = " and ".join(authors_strings)
    authors_string = re.sub(r"\s+", " ", authors_string)

    # authors_string = PrepRecord.format_author_field(authors_string)
    record_dict.update(author=authors_string)

    try:
        if "published-print" in item:
            date_parts = item["published-print"]["date-parts"]
            record_dict.update(year=str(date_parts[0][0]))
        elif "published" in item:
            date_parts = item["published"]["date-parts"]
            record_dict.update(year=str(date_parts[0][0]))
        elif "published-online" in item:
            date_parts = item["published-online"]["date-parts"]
            record_dict.update(year=str(date_parts[0][0]))
    except KeyError:
        pass

    retrieved_pages = item.get("page", "")
    if retrieved_pages:
        # DOI data often has only the first page.
        if (
            not record_dict.get("pages", "no_pages") in retrieved_pages
            and "-" in retrieved_pages
        ):
            record_dict.update(pages=item["page"])
            record = colrev.record.PrepRecord(data=record_dict)
            record.unify_pages_field()
            record_dict = record.get_data()

    retrieved_volume = item.get("volume", "")
    if not retrieved_volume == "":
        record_dict.update(volume=str(retrieved_volume))

    retrieved_number = item.get("issue", "")
    if "journal-issue" in item:
        if "issue" in item["journal-issue"]:
            retrieved_number = item["journal-issue"]["issue"]
    if not retrieved_number == "":
        record_dict.update(number=str(retrieved_number))

    if "abstract" in item:
        retrieved_abstract = item["abstract"]
        if not retrieved_abstract == "":
            retrieved_abstract = re.sub(r"<\/?jats\:[^>]*>", " ", retrieved_abstract)
            retrieved_abstract = re.sub(r"\s+", " ", retrieved_abstract)
            retrieved_abstract = str(retrieved_abstract).replace("\n", "")
            retrieved_abstract = retrieved_abstract.lstrip().rstrip()
            record_dict.update(abstract=retrieved_abstract)

    if "language" in item:
        record_dict["language"] = item["language"]
        # convert to ISO 639-3
        # gh_issue https://github.com/geritwagner/colrev/issues/64
        # other languages/more systematically
        if "en" == record_dict["language"]:
            record_dict["language"] = record_dict["language"].replace("en", "eng")

    if (
        not any(x in item for x in ["published-print", "published"])
        # and "volume" not in record_dict
        # and "number" not in record_dict
        and "year" in record_dict
    ):
        record_dict.update(published_online=record_dict["year"])
        record_dict.update(year="forthcoming")

    if "is-referenced-by-count" in item:
        record_dict["cited_by"] = item["is-referenced-by-count"]

    if "update-to" in item:
        for update_item in item["update-to"]:
            if update_item["type"] == "retraction":
                record_dict["warning"] = "retracted"

    for key, value in record_dict.items():
        record_dict[key] = str(value).replace("{", "").replace("}", "")
        if key in ["colrev_masterdata_provenance", "colrev_data_provenance", "doi"]:
            continue
        # Note : some dois (and their provenance) contain html entities
        record_dict[key] = html.unescape(str(value))

    if "ENTRYTYPE" not in record_dict:
        record_dict["ENTRYTYPE"] = "misc"

    return record_dict


# TODO : the following may be integrated into settings.SearchSource
# Keeping in mind the need for lock-mechanisms, e.g., in concurrent prep operations
class GeneralOriginFeed:
    """A general-purpose Origin feed"""

    # pylint: disable=too-many-instance-attributes

    def __init__(
        self,
        *,
        source_operation: colrev.operation.Operation,
        search_source_interface: colrev.env.package_manager.SearchSourcePackageEndpointInterface,
        update_only: bool,
    ):

        self.source = search_source_interface.search_source
        self.feed_file = search_source_interface.search_source.filename

        # Note: the source_identifier identifies records in the search feed.
        # This could be a doi or link or database-specific ID (like WOS accession numbers)
        # The source_identifier can be stored in the main records.bib (it does not have to)
        # The record source_identifier (feed-specific) is used in search
        # or other operations (like prep)
        # In search operations, records are added/updated based on available_ids
        # (which maps source_identifiers to IDs used to generate the colrev_origin)
        # In other operations, records are linked through colrev_origins,
        # i.e., there is no need to store the source_identifier in the main records (redundantly)
        self.source_identifier = search_source_interface.source_identifier

        self.update_only = update_only

        self.__available_ids = {}
        self.__max_id = 1
        if not self.feed_file.is_file():
            self.feed_records = {}
        else:
            with open(self.feed_file, encoding="utf8") as bibtex_file:
                self.feed_records = (
                    source_operation.review_manager.dataset.load_records_dict(
                        load_str=bibtex_file.read()
                    )
                )

            self.__available_ids = {
                x[self.source_identifier]: x["ID"]
                for x in self.feed_records.values()
                if self.source_identifier in x
            }
            self.__max_id = (
                max(
                    [
                        int(x["ID"])
                        for x in self.feed_records.values()
                        if x["ID"].isdigit()
                    ]
                    + [1]
                )
                + 1
            )
        self.source_operation = source_operation
        self.origin_prefix = self.source.get_origin_prefix()

    def save_feed_file(self) -> None:
        """Save the feed file"""

        search_operation = self.source_operation.review_manager.get_search_operation()
        if len(self.feed_records) > 0:

            self.feed_file.parents[0].mkdir(parents=True, exist_ok=True)
            self.source_operation.review_manager.dataset.save_records_dict_to_file(
                records=self.feed_records, save_path=self.feed_file
            )

            while True:
                search_operation.review_manager.load_settings()
                if self.source.filename.name not in [
                    s.filename.name
                    for s in search_operation.review_manager.settings.sources
                ]:
                    search_operation.review_manager.settings.sources.append(self.source)
                    search_operation.review_manager.save_settings()

                try:
                    search_operation.review_manager.dataset.add_changes(
                        path=self.feed_file
                    )
                    break
                except (FileExistsError, OSError):
                    search_operation.review_manager.logger.debug("Wait for git")
                    time.sleep(randint(1, 15))

    def set_id(self, *, record_dict: dict) -> dict:
        """Set incremental record ID
        If self.source_identifier is in record_dict, it is updated, otherwise added as a new record.
        """

        if record_dict[self.source_identifier] in self.__available_ids:
            record_dict["ID"] = self.__available_ids[
                record_dict[self.source_identifier]
            ]
        else:
            record_dict["ID"] = str(self.__max_id).rjust(6, "0")

        return record_dict

    def add_record(self, *, record: colrev.record.Record) -> bool:
        """Add a record to the feed and set its colrev_origin"""

        # Feed:
        feed_record_dict = record.data.copy()
        added_new = True
        if feed_record_dict[self.source_identifier] in self.__available_ids:
            added_new = False
        else:
            self.__max_id += 1

        if "colrev_data_provenance" in feed_record_dict:
            del feed_record_dict["colrev_data_provenance"]
        if "colrev_masterdata_provenance" in feed_record_dict:
            del feed_record_dict["colrev_masterdata_provenance"]
        if "colrev_status" in feed_record_dict:
            del feed_record_dict["colrev_status"]

        if self.update_only and added_new:
            added_new = False
        else:
            self.__available_ids[
                feed_record_dict[self.source_identifier]
            ] = feed_record_dict["ID"]
            self.feed_records[feed_record_dict["ID"]] = feed_record_dict

        # Original record
        colrev_origin = f"{self.origin_prefix}/{record.data['ID']}"
        record.data["colrev_origin"] = [colrev_origin]
        record.add_provenance_all(source=colrev_origin)

        return added_new


if __name__ == "__main__":
    pass
