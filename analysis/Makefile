.PHONY : run status search backward_search cleanse_records screen data

help :
	@echo "Usage: make [command]"
	@echo "    help"
	@echo "        Show this help description"
	@echo "    run"
	@echo "        Run analyses of the complete repository"

run : status search cleanse_records screen data

initialize :
	docker run -ti \
	--volume "$(PWD)":/opt/workdir \
	--user `id -u`:`id -g` \
	review_template_python3 \
	python3 analysis/initialize.py

status :
	docker run -ti \
	--volume "$(PWD)":/opt/workdir \
	--user `id -u`:`id -g` \
	review_template_python3 \
	python3 analysis/status.py

reformat_bibliography :
	docker run -ti \
	--volume "$(PWD)":/opt/workdir \
	--user `id -u`:`id -g` \
	review_template_python3 \
	python3 analysis/reformat_bibliography.py

trace_hash_id :
	docker run -ti \
	--volume "$(PWD)":/opt/workdir \
	--user `id -u`:`id -g` \
	review_template_python3 \
	python3 analysis/trace_hash_id.py

trace_entry :
	docker run -ti \
	--volume "$(PWD)":/opt/workdir \
	--user `id -u`:`id -g` \
	review_template_python3 \
	python3 analysis/trace_entry.py

combine_individual_search_results :
	docker run -ti \
	--volume "$(PWD)":/opt/workdir \
	--user `id -u`:`id -g` \
	review_template_python3 \
	python3 analysis/combine_individual_search_results.py

backward_search : backward_search_prep  backward_search_grobid backward_search_process

backward_search_prep :
	docker run -ti \
	--volume "$(PWD)":/opt/workdir \
	--user `id -u`:`id -g` \
	review_template_python3 \
	python3 analysis/backward_search_prep.py

backward_search_grobid :
	echo "\n WARNING: backward_search_grobid still implemented outside Docker\n" && \
	cd .. && \
	python3 analysis/backward_search_grobid.py

backward_search_process :
	docker run -ti \
	--volume "$(PWD)":/opt/workdir \
	--user `id -u`:`id -g` \
	review_template_python3 \
	python3 analysis/backward_search_process.py

cleanse_records :
	docker run -ti \
	--volume "$(PWD)":/opt/workdir \
	--user `id -u`:`id -g` \
	review_template_python3 \
	python3 analysis/cleanse_records.py

pre_merging_quality_check :
	docker run -ti \
	--volume "$(PWD)":/opt/workdir \
	--user `id -u`:`id -g` \
	review_template_python3 \
	python3 analysis/pre_merging_quality_check.py

extract_manual_pre_merging_edits :
	docker run -ti \
	--volume "$(PWD)":/opt/workdir \
	--user `id -u`:`id -g` \
	review_template_python3 \
	python3 analysis/extract_manual_pre_merging_edits.py

merge_duplicates :
	docker run -ti \
	--volume "$(PWD)":/opt/workdir \
	--user `id -u`:`id -g` \
	review_template_python3 \
	python3 analysis/merge_duplicates.py

screen_sheet :
	docker run -ti \
	--volume "$(PWD)":/opt/workdir \
	--user `id -u`:`id -g` \
	review_template_python3 \
	python3 analysis/screen_sheet.py

acquire_pdfs :
	docker run -ti \
	--volume "$(PWD)":/opt/workdir \
	--user `id -u`:`id -g` \
	review_template_python3 \
	python3 analysis/acquire_pdfs.py

validate_pdfs :
	docker run -ti \
	--volume "$(PWD)":/opt/workdir \
	--user `id -u`:`id -g` \
	review_template_python3 \
	python3 analysis/validate_pdfs.py

screen_1 :
	docker run -ti \
	--volume "$(PWD)":/opt/workdir \
	--user `id -u`:`id -g` \
	review_template_python3 \
	python3 analysis/screen_1.py

screen_2 :
	docker run -ti \
	--volume "$(PWD)":/opt/workdir \
	--user `id -u`:`id -g` \
	review_template_python3 \
	python3 analysis/screen_2.py

data_sheet :
	docker run -ti \
	--volume "$(PWD)":/opt/workdir \
	--user `id -u`:`id -g` \
	review_template_python3 \
	python3 analysis/data_sheet.py

data_pages :
	docker run -ti \
	--volume "$(PWD)":/opt/workdir \
	--user `id -u`:`id -g` \
	review_template_python3 \
	python3 analysis/data_pages.py
