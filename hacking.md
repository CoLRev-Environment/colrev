
#Aufgaben
##Robert
validate input from user
update publication types: no string input, but multiple choice list from API
##Amadu
2 und 4
##Louis
1
##Peter
3

#FRAGEN FUER HACKING SESSIONS
GENERELL: Was muss bis zum 20.12. alles stehen? 
	Was darf noch nach dem pull Date verändert werden?
	Wie wird die Präsi aufgebaut sein? PPP oder frei mit Shell?

crossref.py Zeile 77: __crossref_md_filename = Path("data/search/md_crossref.bib")
	Was genau ist diese Datei, wo findet man sie?
	Kann man mehrere Suchen (unterschiedliche Suchparameter in dieser Datei speichern oder werden hier die 
		Feeds gespeichert? Oder was ganz anderes?
	Settings Search Source wie funktioniert das speichern einer result file

api key format validierung: Welches Format hat ein API key bei Semantic Scholar? Wir würden das gerne validieren
#NEXT STEPS
1) Wie speichert man die Search Source "Semantic Scholar" im colrev Projekt - damit die wiederholt abgerufen werdne kann.
	Welche Parameter braucht diese Funktion?
2) Wie und wo speichern wie die Ergebnisse korrekt (results)?
	Wie funktioniert: Update existing record?
3) Wie aktualliseren wir den feed korrekt?
	wie rerun?
4) Wie baut man den header der URL für semantic scholar (damit der api key genutzt werden kann)


#PUSH-ANLEITUNG
--> diese zeile wurde geändert ... pushtest 
	#speichern
	#git add ...dateiname
	#git commit -m "was geändert wurde hier eingeben"
	#git push


#Utils- KLasse

"""Utility to transform items from semanticscholar into records"""

from __future__ import annotations

import html
import re

import colrev.exceptions as colrev_exceptions
from colrev.constants import Fields
from colrev.constants import ENTRYTYPES
from colrev.constants import FieldValues

#pylint: disable=duplicate-code

def __convert_entry_types(*, entrytype: str) -> ENTRYTYPES:
    """Method to convert semanticscholar entry types to colrev entry types"""
    
    if entrytype == "JournalArticle":
        return ENTRYTYPES.ARTICLE
    elif entrytype == "Book":
        return ENTRYTYPES.BOOK
    elif entrytype == "BookSection":
        return ENTRYTYPES.INBOOK
    elif entrytype == "CaseReport":
        return ENTRYTYPES.TECHREPORT
    else:
        return ENTRYTYPES.MISC


def __item_to_record(*, item) -> dict:
    """Method to convert the different fields and information within item to record dictionary"""
    
    record_dict = dict(item)

    record_dict[Fields.ID] = record_dict.get("paperId")
    record_dict[Fields.DOI] = record_dict.get("externalIds")

    if isinstance(record_dict[Fields.DOI], dict):
        if len(record_dict[Fields.DOI]) > 0:
            record_dict[Fields.DOI] = record_dict[Fields.DOI].get("DOI")
        else:
            record_dict[Fields.DOI] = "n/a"
    assert isinstance(record_dict.get("doi", ""), str)

    record_dict[Fields.ENTRYTYPE] = record_dict.get("publicationTypes")

    if isinstance(record_dict[Fields.ENTRYTYPE], list):
        if len(record_dict[Fields.ENTRYTYPE]) > 0:
            record_dict[Fields.ENTRYTYPE] = record_dict[Fields.ENTRYTYPE][0]
        else:
            record_dict[Fields.ENTRYTYPE] = "n/a"
    assert isinstance(record_dict.get("ENTRYTYPE", ""), str)

    record_dict[Fields.ENTRYTYPE] = __convert_entry_types(entrytype=record_dict.get("ENTRYTYPE"))

    # TO DO: Keep implementing further fields!!

    
    

def __remove_fields(*, record: dict) -> None:
    """Method to remove unsupported fields from semanticscholar record"""

def s2_dict_to_record(*, item: dict) -> dict:
    """Convert a semanticscholar item to a record dict"""

    try:
        record_dict = __item_to_record(item=item)
        __remove_fields(record=record_dict)
        #TO DO: Implement further functions, especially "remove fields": Use colrev/colrev/ops/built_in/search_sources/utils.py as inspiration!
    
    except (IndexError, KeyError) as exc:
        raise colrev_exceptions.RecordNotParsableException(
            f"Exception: Record not parsable: {exc}"
        ) from exc
    
    return record_dict


