#! /usr/bin/env python
import pprint
import re
import typing
import unicodedata

from nameparser import HumanName

from colrev_core.process import RecordState


class Record:

    identifying_fields = [
        "title",
        "author",
        "year",
        "journal",
        "booktitle",
        "volume",
        "issue",
        "pages",
    ]
    pp = pprint.PrettyPrinter(indent=4, width=140, compact=False)

    def __init__(self, data: dict):
        # Note : do not automatically create colrev_ids
        # or at least keep in mind that this will not be possible for some records
        if "colrev_id" in data:
            if isinstance(data["colrev_id"], str):
                data["colrev_id"] = [
                    cid.lstrip() for cid in data["colrev_id"].split(";")
                ]
        self.data = data

    def __repr__(self):
        # TODO : maybe print as OrderedDict
        return self.pp.pformat(self.data)

    def __str__(self):
        # TODO : maybe print as OrderedDict
        return self.pp.pformat(self.data)

    def get_origins(self) -> list:
        if "origin" in self.data:
            origins = self.data["origin"].split(";")
        else:
            origins = []
        return origins

    def shares_origins(self, other_record) -> bool:
        return any(x in other_record.get_origins() for x in self.get_origins())

    def get_data(self) -> dict:
        return self.data

    def get_field(self, field_key):
        return self.data[field_key]

    def update_field(self, field, value, source, confidence):
        self.data["field"] = value
        if field in self.identifying_fields:
            # TODO: replace if already exists
            self.data[
                "provenance_identifying_fields"
            ] = f"{field}:{source};{confidence}"
        else:
            self.data["provenance_additional_fields"] = f"{field}:{source};{confidence}"
        return

    def add_colrev_ids(self, records: typing.List[dict]):

        for r in records:
            try:
                colrev_id = self.create_colrev_id(alsoKnownAsRecord=r)
                if "colrev_id" not in self.data:
                    self.data["colrev_id"] = [colrev_id]
                elif colrev_id not in self.data["colrev_id"]:
                    self.data["colrev_id"].append(colrev_id)
            except NotEnoughDataToIdentifyException:
                pass

        return

    @classmethod
    def __robust_append(cls, input_string: str, to_append: str) -> str:
        input_string = str(input_string)
        to_append = (
            str(to_append).replace("\n", " ").rstrip().lstrip().replace("–", " ")
        )
        to_append = re.sub(r"[\.\:“”’]", "", to_append)
        to_append = re.sub(r"\s+", "-", to_append)
        to_append = to_append.lower()
        input_string = input_string + "|" + to_append
        return input_string

    @classmethod
    def __rmdiacritics(cls, char):
        """
        Return the base character of char, by "removing" any
        diacritics like accents or curls and strokes and the like.
        """
        try:
            desc = unicodedata.name(char)
            cutoff = desc.find(" WITH ")
            if cutoff != -1:
                desc = desc[:cutoff]
                char = unicodedata.lookup(desc)
        except (KeyError, ValueError):
            pass  # removing "WITH ..." produced an invalid name
        return char

    @classmethod
    def __remove_accents(cls, input_str: str) -> str:
        nfkd_form = unicodedata.normalize("NFKD", input_str)
        wo_ac = [
            cls.__rmdiacritics(c) for c in nfkd_form if not unicodedata.combining(c)
        ]
        wo_ac_str = "".join(wo_ac)
        return wo_ac_str

    @classmethod
    def __get_container_title(cls, record: dict) -> str:

        # school as the container title for theses
        if record["ENTRYTYPE"] in ["phdthesis", "masterthesis"]:
            container_title = record["school"]
        # for technical reports
        elif "techreport" == record["ENTRYTYPE"]:
            container_title = record["institution"]
        elif "inproceedings" == record["ENTRYTYPE"]:
            container_title = record["booktitle"]
        elif "article" == record["ENTRYTYPE"]:
            container_title = record["journal"]
        else:
            raise KeyError
        # TODO : TBD how to deal with the other ENTRYTYPES
        # if "series" in record:
        #     container_title += record["series"]
        # if "url" in record and not any(
        #     x in record for x in ["journal", "series", "booktitle"]
        # ):
        #     container_title += record["url"]

        return container_title

    @classmethod
    def __format_author_field(cls, input_string: str) -> str:
        input_string = input_string.replace("\n", " ").replace("'", "")
        names = cls.__remove_accents(input_string).replace("; ", " and ").split(" and ")
        author_list = []
        for name in names:

            if "," == name.rstrip()[-1:]:
                # if last-names only (eg, "Webster, and Watson, ")
                if len(name[:-2]) > 1:
                    author_list.append(str(name.rstrip()[:-1]))
            else:
                parsed_name = HumanName(name)
                # Note: do not set parsed_name.string_format as a global constant
                # to preserve consistent creation of identifiers
                parsed_name.string_format = "{last} "
                if len(parsed_name.middle) > 0:
                    parsed_name.middle = parsed_name.middle[:1]
                if len(parsed_name.first) > 0:
                    parsed_name.first = parsed_name.first[:1]
                if len(parsed_name.nickname) > 0:
                    parsed_name.nickname = ""

                if len(str(parsed_name)) > 1:
                    author_list.append(str(parsed_name))

        return "-".join(author_list)

    def create_colrev_id(
        self, alsoKnownAsRecord: dict = {}, assume_complete=False
    ) -> str:
        """Returns the colrev_id of the Record.
        If a alsoKnownAsRecord is provided, it returns the colrev_id of the
        alsoKnownAsRecord (using the Record as the reference to decide whether
        required fields are missing)"""

        if not assume_complete:
            if self.data["status"] in [
                RecordState.md_imported,
                RecordState.md_needs_manual_preparation,
            ]:
                if len(alsoKnownAsRecord) != 0:
                    raise NotEnoughDataToIdentifyException(
                        "cannot determine field requirements "
                        "(e.g., volume/number for journal articles)"
                    )

        if len(alsoKnownAsRecord) == 0:
            record = self.data
        else:
            # TODO : need a better design for selecting required fields
            required_fields = [
                k
                for k in self.data.keys()
                if k
                in [
                    "author",
                    "title",
                    "year",
                    "journal",
                    "volume",
                    "number",
                    "pages",
                    "booktitle",
                    # chapter, school, ...
                ]
            ]

            missing_fields = [f for f in required_fields if f not in alsoKnownAsRecord]
            if len(missing_fields) > 0:
                raise NotEnoughDataToIdentifyException(",".join(missing_fields))
            record = alsoKnownAsRecord

        try:

            # Including the version of the identifier prevents cases
            # in which almost all identifiers are identical
            # (and very few identifiers change)
            # when updating the identifier function function
            # (this may look like an anomaly and be hard to identify)
            srep = "colrev_id1:"
            if "article" == record["ENTRYTYPE"].lower():
                srep = self.__robust_append(srep, "a")
            elif "inproceedings" == record["ENTRYTYPE"].lower():
                srep = self.__robust_append(srep, "p")
            else:
                srep = self.__robust_append(srep, record["ENTRYTYPE"].lower())
            srep = self.__robust_append(srep, self.__get_container_title(record))
            if "article" == record["ENTRYTYPE"]:
                # Note: volume/number may not be required.
                # TODO : how do we make sure that colrev_ids are not generated when
                # volume/number are required?
                srep = self.__robust_append(srep, record.get("volume", "-"))
                srep = self.__robust_append(srep, record.get("number", "-"))
            srep = self.__robust_append(srep, record["year"])
            author = self.__format_author_field(record["author"])
            if "" == author.replace("-", ""):
                raise NotEnoughDataToIdentifyException("author field format error")
            srep = self.__robust_append(srep, author)
            title_str = re.sub("[^0-9a-zA-Z]+", " ", record["title"])
            srep = self.__robust_append(srep, title_str)
            srep = srep.replace("&", "and")

            # Note : pages not needed.
            # pages = record.get("pages", "")
            # srep = self.__robust_append(srep, pages)
        except KeyError as e:
            raise NotEnoughDataToIdentifyException(str(e))
        return srep


class NotEnoughDataToIdentifyException(Exception):
    def __init__(self, msg: str = None):
        self.message = msg
        super().__init__(self.message)


if __name__ == "__main__":
    pass
