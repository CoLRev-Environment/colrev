.PHONY : status search backward_search cleanse_records screen data

# Note: this should not be necessary for the pip-version (when the scripts can simply access the current path as the working directory)
DATA_PATH=data

help :
	@echo "Usage: make [command]"
	@echo "    help"
	@echo "        Show this help description"

cli :
	docker-compose up & gnome-terminal -e "bash -c \"docker-compose run --rm review_template_python3 /bin/bash\""

initialize :
	cd $(DATA_PATH) && python3 ../analysis/initialize.py

validate :
	cd $(DATA_PATH) && pre-commit run -a

status :
	cd $(DATA_PATH) && python3 ../analysis/status.py

reformat_bibliography :
	cd $(DATA_PATH) && python3 ../analysis/reformat_bibliography.py

trace_hash_id :
	cd $(DATA_PATH) && python3 ../analysis/trace_hash_id.py

trace_search_result :
	cd $(DATA_PATH) && python3 ../analysis/trace_search_result.py

# to test:

trace_entry :
	cd $(DATA_PATH) && python3 ../analysis/trace_entry.py

combine_individual_search_results :
	cd $(DATA_PATH) && python3 ../analysis/combine_individual_search_results.py

cleanse_records :
	cd $(DATA_PATH) && python3 ../analysis/cleanse_records.py

screen_sheet :
	cd $(DATA_PATH) && python3 ../analysis/screen_sheet.py

screen_1 :
	cd $(DATA_PATH) && python3 ../analysis/screen_1.py

screen_2 :
	cd $(DATA_PATH) && python3 ../analysis/screen_2.py

data_sheet :
	cd $(DATA_PATH) && python3 ../analysis/data_sheet.py

data_pages :
	cd $(DATA_PATH) && python3 ../analysis/data_pages.py

backward_search :
	cd $(DATA_PATH) && python3 ../analysis/backward_search.py

merge_duplicates :
	cd $(DATA_PATH) && python3 ../analysis/merge_duplicates.py

acquire_pdfs :
	cd $(DATA_PATH) && python3 ../analysis/acquire_pdfs.py

# development:

fix_errors :
	cd $(DATA_PATH) && python3 ../analysis/fixing_errors.py

validate_pdfs :
	cd $(DATA_PATH) && python3 ../analysis/validate_pdfs.py

sample_profile :
	cd $(DATA_PATH) && python3 ../analysis/sample_profile.py
