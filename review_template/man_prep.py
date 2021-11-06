#! /usr/bin/env python
import os
import pprint

import git

from review_template import prepare
from review_template import repo_setup
from review_template import utils


record_type_mapping = {'a': 'article', 'p': 'inproceedings',
                       'b': 'book', 'ib': 'inbook', 'pt': 'phdthesis',
                       'mt': 'masterthesis',
                       'o': 'other', 'unp': 'unpublished'}

ID_list = []


def print_record(record):
    pp = pprint.PrettyPrinter(indent=4, width=140)
    # Escape sequence to clear terminal output for each new comparison
    os.system('cls' if os.name == 'nt' else 'clear')
    pp.pprint(record)
    if 'title' in record:
        print('https://scholar.google.de/scholar?hl=de&as_sdt=0%2C5&q=' +
              record['title'].replace(' ', '+'))
    return


def man_correct_recordtype(record):

    if 'n' == input('ENTRYTYPE=' + record['ENTRYTYPE'] + ' correct?'):
        choice = input('Correct type: ' +
                       'a (article), p (inproceedings), ' +
                       'b (book), ib (inbook), ' +
                       'pt (phdthesis), mt (masterthesis), '
                       'unp (unpublished), o (other), ')
        assert choice in record_type_mapping.keys()
        correct_record_type = [value for (key, value)
                               in record_type_mapping.items()
                               if key == choice]
        record['ENTRYTYPE'] = correct_record_type[0]
    return record


def man_provide_required_fields(record):
    if prepare.is_complete(record):
        return record

    reqs = prepare.record_field_requirements[record['ENTRYTYPE']]
    for field in reqs:
        if field not in record:
            value = input('Please provide the ' + field + ' (or NA)')
            record[field] = value
    return record


def man_fix_field_inconsistencies(record):
    if not prepare.has_inconsistent_fields(record):
        return record

    print('TODO: ask whether the inconsistent fields can be dropped?')

    return record


def man_fix_incomplete_fields(record):
    if not prepare.has_incomplete_fields(record):
        return record

    print('TODO: ask for completion of fields')
    # organize has_incomplete_fields() values in a dict?

    return record


def man_prep_record(record):

    global ID_list

    if 'needs_manual_preparation' != record['md_status']:
        return record

    print_record(record)

    man_correct_recordtype(record)

    man_provide_required_fields(record)

    man_fix_field_inconsistencies(record)

    man_fix_incomplete_fields(record)

    # Note: for complete_based_on_doi field:
    record = prepare.retrieve_doi_metadata(record)

    if (prepare.is_complete(record) or prepare.is_doi_complete(record)) and \
            not prepare.has_inconsistent_fields(record) and \
            not prepare.has_incomplete_fields(record):
        record = prepare.drop_fields(record)
        record.update(ID=utils.generate_ID_blacklist(
            record, ID_list,
            record_in_bib_db=True,
            raise_error=False))
        ID_list.append(record['ID'])
        record.update(md_status='prepared')
        record.update(metadata_source='MAN_PREP')

    return record


def man_prep_records():
    saved_args = locals()
    global ID_list

    repo = git.Repo('')
    utils.require_clean_repo(repo)

    print('Loading records for manual preparation...')
    bib_db = utils.load_main_refs()

    ID_list = [record['ID'] for record in bib_db.entries]

    for record in bib_db.entries:
        record = man_prep_record(record)
        utils.save_bib_file(bib_db)

    bib_db = utils.set_IDs(bib_db)
    MAIN_REFERENCES = repo_setup.paths['MAIN_REFERENCES']
    utils.save_bib_file(bib_db, MAIN_REFERENCES)
    repo.index.add([MAIN_REFERENCES])

    utils.create_commit(repo, 'Prepare records for import',
                        saved_args,
                        manual_author=True)
    return


def main():
    print('TODO: include processing_reports')
    man_prep_records()
    return


if __name__ == '__main__':
    main()
