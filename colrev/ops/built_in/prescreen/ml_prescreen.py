#! /usr/bin/env python
"""Prescreen based on specified scope"""
from __future__ import annotations

import typing
from dataclasses import dataclass

import zope.interface
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.env.language_service
import colrev.env.local_index
import colrev.env.package_manager
import colrev.exceptions as colrev_exceptions
import colrev.record
from colrev.constants import Fields

import re
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords
from nltk.stem import WordNetLemmatizer
import pandas as pd
from gensim.models.doc2vec import Doc2Vec, TaggedDocument
from sklearn.model_selection import train_test_split
from sklearn.neighbors import KNeighborsClassifier

if typing.TYPE_CHECKING:
    import colrev.ops.prescreen.Prescreen

# pylint: disable=too-few-public-methods
# pylint: disable=duplicate-code

# to check: https://asistdl.onlinelibrary.wiley.com/doi/full/10.1002/asi.24816


@zope.interface.implementer(
    colrev.env.package_manager.PrescreenPackageEndpointInterface
)
@dataclass
class MlPrescreen(JsonSchemaMixin):
    settings_class = colrev.env.package_manager.DefaultSettings
    ci_supported: bool = False
    
    def __init__(
        self,
        *,
        prescreen_operation: colrev.ops.prescreen.Prescreen,  # pylint: disable=unused-argument
        settings: dict,
    ) -> None:
        print ("test")
        self.settings = self.settings_class.load_settings(data=settings)
        self.prescreen_operation = prescreen_operation
        self.review_manager = prescreen_operation.review_manager
  
  
    
    def preprocess_text(self, text):
        if isinstance(text, str): 
            text = text.lower()
            text = re.sub(r'[^a-z\s]', '', text)
            tokens = word_tokenize(text)
            stop_words = set(stopwords.words('english'))
            tokens = [word for word in tokens if word not in stop_words]
            lemmatizer = WordNetLemmatizer()
            stemmed_tokens = [lemmatizer.lemmatize(word) for word in tokens]
            preprocessed_text = ' '.join(stemmed_tokens)
            return preprocessed_text
        else:
            return ''

    def parse_bibtex_training(self, bibtex_file):
        data = {"title": [], "abstract": [], "label_included": []}
        with open(bibtex_file, "r", encoding="utf-8") as file:
            bibtex_entries = file.read()
        for entry in bibtex_entries.split("\n\n"):
            if not entry.strip():
                continue
            bib_dict = {}
            for line in entry.split("\n"):
                if "=" in line: 
                    key, value = [x.strip() for x in line.split("=", 1)]
                    bib_dict[key] = value
            colrev_status = bib_dict.get("colrev_status", "")
            if colrev_status.startswith("{rev_"):
                data["title"].append(self.preprocess_text(bib_dict.get("title", "")))
                data["abstract"].append(self.preprocess_text(bib_dict.get("abstract", "")))
                data["label_included"].append(1 if "{rev_synthesized}" in colrev_status or "{rev_included}" in colrev_status else 0)

        df = pd.DataFrame(data)
        return df


    def train_model(self, df):
        documents = [TaggedDocument(words=word_tokenize(str(title) + ' ' + str(abstract)), tags=[str(i)]) for i, (title, abstract, _) in enumerate(zip(df['title'], df['abstract'], df['label_included']))]
        model = Doc2Vec(vector_size=300, window=5, min_count=4, dm=0, epochs=30, seed=42)
        model.build_vocab(documents)
        model.train(documents, total_examples=model.corpus_count, epochs=10)
        return model

    def apply_model(self, df, model):
        vectors = [model.infer_vector(doc) for doc in df[["title", "abstract"]].values]
        return vectors

    def create_and_predict_dataframe(self, bibtex_file):
        data = {"colrev_origin": [], "title": [], "abstract": []}
        with open(bibtex_file, "r", encoding="utf-8") as file:
            bibtex_entries = file.read()
        entries = [entry.strip() for entry in bibtex_entries.split("\n\n") if entry.strip()]
        for entry in entries:
            bib_dict = {}
            current_key = None
            current_value = ""
            for line in entry.split("\n"):
                if "=" in line:
                    key, value = [x.strip() for x in line.split("=", 1)]
                    bib_dict[key] = value
                    current_key = key
                    current_value = value
                elif current_key is not None:
                    current_value += line.strip()
                    bib_dict[current_key] = current_value
            colrev_status = bib_dict.get("colrev_status", "")
            if colrev_status.startswith("{md_"):
                data["colrev_origin"].append(bib_dict.get("colrev_origin", ""))
                data["title"].append(self.preprocess_text(bib_dict.get("title", "")))
                data["abstract"].append(self.preprocess_text(bib_dict.get("abstract", "")))
        df = pd.DataFrame(data)
        return df


    def _ml_prescreen(self) -> bool:
        df = self.parse_bibtex_training("data/records.bib")
        X_train = df[df["label_included"] == 1][["title", "abstract"]]
        y_train = df[df["label_included"] == 1]["label_included"]
        model = self.train_model(df)
        knn_classifier = KNeighborsClassifier(n_neighbors=2, weights='uniform', metric='euclidean')
        knn_classifier.fit(self.apply_model(X_train, model), y_train)
        md_df = self.create_and_predict_dataframe("data/records.bib")
        md_vectors = self.apply_model(md_df[["title", "abstract"]], model)
        md_predictions = knn_classifier.predict(md_vectors)
        prediction_data = {}
        for index, prediction in zip(md_df.index, md_predictions):
            colrev_origin = md_df.loc[index, "colrev_origin"]
            if colrev_origin not in prediction_data:
                prediction_data[colrev_origin] = {"colrev_origin": colrev_origin}
            if prediction == 1:
                prediction_data[colrev_origin]["colrev_status"] = "{rev_prescreen_included}"
            else:
                prediction_data[colrev_origin]["colrev_status"] = "{rev_prescreen_excluded}"
        for key, value in prediction_data.items():
            colrev_origin = value.get('colrev_origin', None)
            if colrev_origin is not None:
                cleaned_prediction_key = [item.strip().rstrip(',') for item in colrev_origin.replace('{', '').replace('}', '').split(';') if item.strip() != '' and item.strip() != ',']
                pre_str = str(cleaned_prediction_key)
                prescreen_data = self.prescreen_operation.get_data()
                for record_dict in prescreen_data["items"]:
                    org_str = str(record_dict.get("colrev_origin", []))
                    if pre_str in org_str:
                        if value.get("colrev_status") == "{rev_prescreen_included}":
                            inclusion_decision = True
                        else:
                            inclusion_decision = False
                        padding = prescreen_data["PAD"]
                        record = colrev.record.Record(data=record_dict)
                        self.prescreen_operation.prescreen(
                            record=record,
                            prescreen_inclusion=inclusion_decision,
                            PAD=padding,
                        )
   
   
   
    def run_prescreen(
        self,
        records: dict,
        split: list,  # pylint: disable=unused-argument
    ) -> dict:
        """Prescreen records based on the ML"""
        print ("test2")
        for record_dict in records.values():
            self.__conditional_prescreen(
                record_dict=record_dict,
            )
        print ("hiiiiii")
        self._ml_prescreen()
        return records

