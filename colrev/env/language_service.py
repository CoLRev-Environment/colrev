#! /usr/bin/env python
"""Service to detect languages and handle language codes"""
from __future__ import annotations

import pycountry
from lingua.builder import LanguageDetectorBuilder

import colrev.exceptions as colrev_exceptions
import colrev.record


class LanguageService:
    """Service to detect languages and handle language codes"""

    __eng_false_negatives = ["editorial", "introduction"]

    def __init__(self) -> None:
        # Note : Lingua is tested/evaluated relative to other libraries:
        # https://github.com/pemistahl/lingua-py
        # It performs particularly well for short strings (single words/word pairs)
        # The langdetect library is non-deterministic, especially for short strings
        # https://pypi.org/project/langdetect/

        self.__lingua_language_detector = (
            LanguageDetectorBuilder.from_all_languages_with_latin_script().build()
        )

        # Language formats: ISO 639-1 standard language codes
        # https://pypi.org/project/langcodes/
        # https://github.com/flyingcircusio/pycountry

        self.__lang_code_mapping = {}
        for country in pycountry.languages:
            self.__lang_code_mapping[country.name.lower()] = country.alpha_3

    def compute_language(self, *, text: str) -> str:
        """Compute the most likely language code"""

        if text.lower() in self.__eng_false_negatives:
            return "eng"

        language = self.__lingua_language_detector.detect_language_of(text)
        if language:
            return language.iso_code_639_3.name.lower()
        return ""

    def compute_language_confidence_values(self, *, text: str) -> list:
        """Computes the most likely languages of a string and their language codes"""

        if text.lower() in self.__eng_false_negatives:
            return [("eng", 1.0)]

        predictions = (
            self.__lingua_language_detector.compute_language_confidence_values(
                text=text
            )
        )
        predictions_unified = []
        for lang, conf in predictions:
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
        self, *, record: colrev.record.Record
    ) -> None:
        """Unifies a language_code string to the ISO 639-3 standard"""

        if "language" not in record.data:
            return

        if record.data["language"].lower() in ["en"]:
            record.data["language"] = "eng"

        elif record.data["language"].lower() in ["fr"]:
            record.data["language"] = "fra"

        elif record.data["language"].lower() in ["ar"]:
            record.data["language"] = "ara"

        elif record.data["language"].lower() in ["de"]:
            record.data["language"] = "deu"

        if 3 != len(record.data["language"]):
            if record.data["language"].lower() in self.__lang_code_mapping:
                record.data["language"] = self.__lang_code_mapping[
                    record.data["language"].lower()
                ]

        self.validate_iso_639_3_language_codes(lang_code_list=[record.data["language"]])


if __name__ == "__main__":
    pass
