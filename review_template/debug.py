import configparser
import logging
import os
import pprint

from bibtexparser.bparser import BibTexParser
from bibtexparser.customization import convert_to_unicode


def set_debug_mode(activate: bool) -> None:

    config_path = "private_config.ini"
    private_config = configparser.ConfigParser()
    if os.path.exists(config_path):
        private_config.read(config_path)
    if "general" not in private_config.sections():
        private_config.add_section("general")
    if activate:
        private_config["general"]["debug_mode"] = "yes"
    else:
        private_config["general"]["debug_mode"] = "no"
    with open(config_path, "w") as f:
        private_config.write(f)

    logging.info(f"Set debug mode to {activate}")

    return


def main():

    # insert test code

    from review_template import prepare, review_manager

    # from review_template.review_manager import RecordState

    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    review_manager.config["DEBUG_MODE"] = True

    pp = pprint.PrettyPrinter(indent=4, width=140, compact=False)

    origin = "2021-11-17-dblp_journals_jmis.bib/0000000533"
    filepath = origin.split("/")[0]
    with open("INSERT_PATH" + filepath) as target_db:

        bib_db = BibTexParser(
            customization=convert_to_unicode,
            ignore_nonstandard_types=False,
            common_strings=True,
        ).parse_file(target_db, partial=True)

    record = [r for r in bib_db.entries if origin.split("/")[1] == r["ID"]][0]

    # with open('bibtex.bib') as bibtex_file:
    #     bibtex_str = bibtex_file.read()
    # status = {md_imported},

    # bibtex_str = """
    # @inbook{034,
    #  status = {md_imported},
    #  author = {Tedeschi, J and Norman, N},
    #  booktitle = {The Self and Social Life},
    #  date = {1985},
    #  editor = {B.R.},
    #  pages = {293--322},
    #  title = {Social power, selfpresentation, and the self},
    #  year = {1985}
    # }
    # """

    # bib_db = bibtexparser.loads(bibtex_str)
    # record = bib_db.entries[0]

    record = prepare.prepare(record)

    pp.pprint(record)

    # {   'ENTRYTYPE': 'inbook',
    #     'ID': '080',
    #     'address': 'Oxford, UK',
    #     'author': 'Zuboff, S',
    #     'booktitle': 'Heinemann Professional',
    #     'status': 'imported',
    #     'title': 'In the age of the smart machine: The future of work and power',
    #     'year': '1988'}

    return
