#! /usr/bin/env python
"""Open Alex API"""
import pyalex
from pyalex import Works

import colrev.env.language_service
import colrev.exceptions as colrev_exceptions
import colrev.record.record_prep
from colrev.constants import ENTRYTYPES
from colrev.constants import Fields
from colrev.constants import FieldValues

# pylint: disable=too-few-public-methods


class OpenAlexAPI:
    """Connector for the Open Alex API"""

    # pylint: disable=too-many-arguments
    def __init__(
        self,
        email: str,
        # session: requests.Session,
        # query: typing.Optional[str] = None,
        # timeout: int = 60,
    ):
        pyalex.config.email = email
        self.language_service = colrev.env.language_service.LanguageService()

    def _fix_errors(self, *, record: colrev.record.record.Record) -> None:
        if "PubMed" == record.data.get(Fields.JOURNAL, ""):
            record.remove_field(key=Fields.JOURNAL)
        try:
            self.language_service.unify_to_iso_639_3_language_codes(record=record)
        except colrev_exceptions.InvalidLanguageCodeException:
            record.remove_field(key=Fields.LANGUAGE)

    def _set_author_from_item(self, *, record_dict: dict, item: dict) -> None:
        author_list = []
        # pylint: disable=colrev-missed-constant-usage
        for author in item["authorships"]:
            if "author" not in author:
                continue
            if author["author"].get("display_name", None) is None:
                continue
            author_string = colrev.record.record_prep.PrepRecord.format_author_field(
                author["author"]["display_name"]
            )
            author_list.append(author_string)

        record_dict[Fields.AUTHOR] = " and ".join(author_list)

    def _parse_item_to_record(self, *, item: dict) -> colrev.record.record.Record:
        def set_entrytype(*, record_dict: dict, item: dict) -> None:
            # pylint: disable=colrev-missed-constant-usage
            if "title" in record_dict and record_dict["title"] is None:
                del record_dict["title"]
            if item.get("type_crossref", "") == "proceedings-article":
                record_dict[Fields.ENTRYTYPE] = ENTRYTYPES.INPROCEEDINGS
                if (
                    item.get("primary_location", None) is not None
                    and item["primary_location"].get("source", None) is not None
                ):
                    display_name = item["primary_location"]["source"]["display_name"]
                    if display_name != "Proceedings":
                        record_dict[Fields.BOOKTITLE] = display_name
            elif item["type"] in ["journal-article", "article"]:
                record_dict[Fields.ENTRYTYPE] = ENTRYTYPES.ARTICLE
                if (
                    item.get("primary_location", None) is not None
                    and item["primary_location"].get("source", None) is not None
                ):
                    record_dict[Fields.JOURNAL] = item["primary_location"]["source"][
                        "display_name"
                    ]
            else:
                record_dict[Fields.ENTRYTYPE] = ENTRYTYPES.MISC

        record_dict = {}
        record_dict["id"] = item["id"].replace("https://openalex.org/", "")
        # pylint: disable=colrev-missed-constant-usage
        if "title" in item and item["title"] is not None:
            record_dict[Fields.TITLE] = item["title"].lstrip("[").rstrip("].")
        set_entrytype(record_dict=record_dict, item=item)

        if "publication_year" in item and item["publication_year"] is not None:
            record_dict[Fields.YEAR] = str(item["publication_year"])
        # pylint: disable=colrev-missed-constant-usage
        if "language" in item and item["language"] is not None:
            record_dict[Fields.LANGUAGE] = item["language"]

        if "is_retracted" in item and item["is_retracted"]:
            record_dict[FieldValues.RETRACTED] = item["is_retracted"]

        # pylint: disable=colrev-missed-constant-usage
        if "doi" in item and item["doi"] is not None:
            record_dict[Fields.DOI] = (
                item["doi"].upper().replace("HTTPS://DOI.ORG/", "")
            )

        record_dict[Fields.CITED_BY] = item["cited_by_count"]

        # pylint: disable=colrev-missed-constant-usage
        if "volume" in item["biblio"] and item["biblio"]["volume"] is not None:
            record_dict[Fields.VOLUME] = item["biblio"]["volume"]
        if "issue" in item["biblio"] and item["biblio"]["issue"] is not None:
            record_dict[Fields.NUMBER] = item["biblio"]["issue"]
        if "first_page" in item["biblio"] and item["biblio"]["first_page"] is not None:
            record_dict[Fields.PAGES] = item["biblio"]["first_page"]
        if "last_page" in item["biblio"] and item["biblio"]["last_page"] is not None:
            record_dict[Fields.PAGES] += "--" + item["biblio"]["last_page"]

        self._set_author_from_item(record_dict=record_dict, item=item)
        record = colrev.record.record.Record(record_dict)

        self._fix_errors(record=record)
        return record

    def get_record(self, *, open_alex_id: str) -> colrev.record.record.Record:
        """Get a record from OpenAlex"""

        item = Works()[open_alex_id]
        retrieved_record = self._parse_item_to_record(item=item)
        return retrieved_record
