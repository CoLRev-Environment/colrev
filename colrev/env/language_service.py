#! /usr/bin/env python
"""Service to detect languages and handle language codes"""
from __future__ import annotations

import re

import pycountry
from lingua import LanguageDetectorBuilder  # pylint: disable=no-name-in-module

import colrev.exceptions as colrev_exceptions
import colrev.record.record
from colrev.constants import Fields


class LanguageService:
    """Service to detect languages and handle language codes"""

    _eng_false_negatives = ["editorial", "introduction"]

    def __init__(self) -> None:
        # Note : Lingua is tested/evaluated relative to other libraries:
        # https://github.com/pemistahl/lingua-py
        # It performs particularly well for short strings (single words/word pairs)
        # The langdetect library is non-deterministic, especially for short strings
        # https://pypi.org/project/langdetect/

        self._lingua_language_detector = (
            LanguageDetectorBuilder.from_all_languages_with_latin_script().build()
        )

        # Language formats: ISO 639-1 standard language codes
        # https://pypi.org/project/langcodes/
        # https://github.com/flyingcircusio/pycountry

        self._lang_code_mapping = {}
        for country in pycountry.languages:
            self._lang_code_mapping[country.name.lower()] = country.alpha_3

    # pylint: disable=too-many-return-statements
    # pylint: disable=too-many-branches
    def _determine_alphabet(self, str_to_check: str) -> str:
        assert len(str_to_check) != 0

        str_to_check = re.sub(r"[\s\d\.\:]*", "", str_to_check)

        nr_greek_letters = 0
        nr_hangul_characters = 0
        nr_cyrillic_characters = 0
        nr_hebrew_characters = 0
        nr_arabic_characters = 0
        nr_chinese_characters = 0
        for character in str_to_check:
            if "\u0370" <= character <= "\u03FF" or "\u1F00" <= character <= "\u1FFF":
                nr_greek_letters += 1
            elif "\uAC00" <= character <= "\uD7A3":
                nr_hangul_characters += 1
            elif "\u0400" <= character <= "\u04FF" or "\u0500" <= character <= "\u052F":
                nr_cyrillic_characters += 1
            elif "\u0590" <= character <= "\u05FF" or "\uFB1D" <= character <= "\uFB4F":
                nr_hebrew_characters += 1
            elif (
                "\u0600" <= character <= "\u06FF"
                or "\u0750" <= character <= "\u077F"
                or "\u08A0" <= character <= "\u08FF"
                or "\uFB50" <= character <= "\uFDFF"
                or "\uFE70" <= character <= "\uFEFF"
            ):
                nr_arabic_characters += 1
            elif "\u4E00" <= character <= "\u9FFF" or "\u3400" <= character <= "\u4DBF":
                nr_chinese_characters += 1
        if nr_greek_letters / len(str_to_check) > 0.75:
            return "ell"
        if nr_hangul_characters / len(str_to_check) > 0.75:
            return "kor"
        if nr_cyrillic_characters / len(str_to_check) > 0.75:
            return "rus"
        if nr_hebrew_characters / len(str_to_check) > 0.75:
            return "heb"
        if nr_arabic_characters / len(str_to_check) > 0.75:
            return "ara"
        if nr_chinese_characters / len(str_to_check) > 0.75:
            return "chi"
        return ""  # pragma: no cover

    def compute_language(self, *, text: str) -> str:
        """Compute the most likely language code"""

        if text.lower() in self._eng_false_negatives:
            return "eng"

        language = self._lingua_language_detector.detect_language_of(text)

        if language:
            # There are too many errors/classifying papers as latin
            if language.iso_code_639_3.name.lower() == "lat":
                return ""
            return language.iso_code_639_3.name.lower()

        return self._determine_alphabet(text)

    def compute_language_confidence_values(self, *, text: str) -> list:
        """Computes the most likely languages of a string and their language codes"""

        if text.lower() in self._eng_false_negatives:
            return [("eng", 1.0)]

        predictions = self._lingua_language_detector.compute_language_confidence_values(
            text=text
        )
        predictions_unified = []
        for prediction in predictions:
            lang = prediction.language
            conf = prediction.value
            predictions_unified.append((lang.iso_code_639_3.name.lower(), conf))

        return predictions_unified

    def validate_iso_639_3_language_codes(self, *, lang_code_list: list) -> None:
        """Validates whether a list of language codes complies with the ISO 639-3 standard"""

        assert isinstance(lang_code_list, list)

        invalid_language_codes = [x for x in lang_code_list if 3 != len(x)]
        if invalid_language_codes:
            raise colrev_exceptions.InvalidLanguageCodeException(
                invalid_language_codes=invalid_language_codes
            )

    def unify_to_iso_639_3_language_codes(
        self, *, record: colrev.record.record.Record
    ) -> None:
        """Unifies a language_code string to the ISO 639-3 standard"""

        if Fields.LANGUAGE not in record.data:
            return

        if record.data[Fields.LANGUAGE].lower() in ["en"]:
            record.data[Fields.LANGUAGE] = "eng"

        elif record.data[Fields.LANGUAGE].lower() in ["fr"]:
            record.data[Fields.LANGUAGE] = "fra"

        elif record.data[Fields.LANGUAGE].lower() in ["ar"]:
            record.data[Fields.LANGUAGE] = "ara"

        elif record.data[Fields.LANGUAGE].lower() in ["de"]:
            record.data[Fields.LANGUAGE] = "deu"

        if len(record.data[Fields.LANGUAGE]) != 3:
            if record.data[Fields.LANGUAGE].lower() in self._lang_code_mapping:
                record.data[Fields.LANGUAGE] = self._lang_code_mapping[
                    record.data[Fields.LANGUAGE].lower()
                ]

        self.validate_iso_639_3_language_codes(
            lang_code_list=[record.data[Fields.LANGUAGE]]
        )
