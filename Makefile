.PHONY : run status search backward_search cleanse_records screen data

help :
	@echo "Usage: make [command]"
	@echo "    help"
	@echo "        Show this help description"
	@echo "    run"
	@echo "        Run analyses of the complete repository"

run :
	$(MAKE) -s -C analysis run


status :
	$(MAKE) -s -C analysis status

reformat_bibliography :
	$(MAKE) -s -C analysis reformat_bibliography

trace_hash_id :
	$(MAKE) -s -C analysis trace_hash_id

trace_entry :
	$(MAKE) -s -C analysis trace_entry

# to test:
combine_individual_search_results :
	$(MAKE) -s -C analysis combine_individual_search_results

cleanse_records :
	$(MAKE) -s -C analysis cleanse_records

screen_sheet :
	$(MAKE) -s -C analysis screen_sheet

screen_1 :
	$(MAKE) -s -C analysis screen_1

screen_2 :
	$(MAKE) -s -C analysis screen_2

data_sheet :
	$(MAKE) -s -C analysis data_sheet

data_pages :
	$(MAKE) -s -C analysis data_pages


# development:

backward_search :
	$(MAKE) -s -C analysis backward_search

backward_search_prep :
	$(MAKE) -s -C analysis backward_search_prep

backward_search_grobid :
	$(MAKE) -s -C analysis backward_search_grobid

backward_search_process :
	$(MAKE) -s -C analysis backward_search_process

pre_merging_quality_check :
	$(MAKE) -s -C analysis pre_merging_quality_check

extract_manual_pre_merging_edits :
	$(MAKE) -s -C analysis extract_manual_pre_merging_edits

merge_duplicates :
	$(MAKE) -s -C analysis merge_duplicates

acquire_pdfs :
	$(MAKE) -s -C analysis acquire_pdfs

validate_pdfs :
	$(MAKE) -s -C analysis validate_pdfs

sample_profile :
	$(MAKE) -s -C analysis/R sample_profile


# To use local instead of shared versions, replace the following and use the code in comments
DOCX_REFERENCE_DOC = --reference-doc /templates/ICIS2021.docx
# DOCX_REFERENCE_DOC = --reference-doc APA-7.docx
LATEX_REF_DOC = --template /templates/basic.tex
# LATEX_REF_DOC = --template basic.tex
CSL_FILE = --csl /styles/mis-quarterly.csl
# CSL_FILE = --csl mis-quarterly.csl
BIBLIOGRAPHY_FILE = --bibliography /bibliography/references.bib
# BIBLIOGRAPHY_FILE = --bibliography references.bib

# The parameters should be in the same document (ideally in the YAML header of paper.md).
# We will keep them in the Makefile until template and reference-doc can be set in the YAML header.
# https://github.com/jgm/pandoc/issues/4627

PANDOC_CALL = docker run --rm \
	--volume "`pwd`:/data" \
	--volume $(shell readlink -f ./styles):/styles/ \
	--volume $(shell readlink -f ./templates):/templates/ \
	--volume $(shell readlink -f ./bibliography):/bibliography/ \
	--user `id -u`:`id -g` \
	pandoc_dockerfile

pdf:
	$(PANDOC_CALL) \
		paper.md \
		--filter pantable \
		--filter pandoc-crossref \
		--citeproc \
		$(BIBLIOGRAPHY_FILE) \
		$(CSL_FILE) \
		$(LATEX_REF_DOC) \
		--pdf-engine xelatex \
		--output paper.pdf

latex:
	$(PANDOC_CALL) \
		paper.md \
		--filter pantable \
		--filter pandoc-crossref \
		--citeproc \
		$(BIBLIOGRAPHY_FILE) \
		$(CSL_FILE) \
		$(LATEX_REF_DOC) \
		--to latex \
		--pdf-engine xelatex \
		--output paper.tex

docx:
	$(PANDOC_CALL) \
		paper.md \
		--filter pantable \
		--filter pandoc-crossref \
		--citeproc \
		$(BIBLIOGRAPHY_FILE) \
		$(CSL_FILE) \
		$(DOCX_REFERENCE_DOC) \
		--output paper.docx
