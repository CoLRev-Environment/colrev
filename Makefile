.PHONY : status search backward_search cleanse_records screen data

help :
	@echo "Usage: make [command]"
	@echo "    help"
	@echo "        Show this help description"

initialize :
	python3 analysis/initialize.py

status :
	python3 analysis/status.py

reformat_bibliography :
	python3 analysis/reformat_bibliography.py

trace_hash_id :
	python3 analysis/trace_hash_id.py

trace_entry :
	python3 analysis/trace_entry.py

# to test:
combine_individual_search_results :
	python3 analysis/combine_individual_search_results.py

cleanse_records :
	python3 analysis/cleanse_records.py

screen_sheet :
	python3 analysis/screen_sheet.py

screen_1 :
	python3 analysis/screen_1.py

screen_2 :
	python3 analysis/screen_2.py

data_sheet :
	python3 analysis/data_sheet.py

data_pages :
	python3 analysis/data_pages.py


# development:

backward_search :
	python3 analysis/backward_search.py

pre_merging_quality_check :
	python3 analysis/pre_merging_quality_check.py

extract_manual_pre_merging_edits :
	python3 analysis/extract_manual_pre_merging_edits.py

merge_duplicates :
	python3 analysis/merge_duplicates.py

acquire_pdfs :
	python3 analysis/acquire_pdfs.py

validate_pdfs :
	python3 analysis/validate_pdfs.py

sample_profile :
	python3 analysis/R sample_profile.py
