ke.PHONY : run status search backward_search cleanse_records screen data

help :
	@echo "Usage: make [command]"
	@echo "    help"
	@echo "        Show this help description"
	@echo "    run"
	@echo "        Run analyses of the complete repository"

run : status search cleanse_records screen data

status :
	docker run -ti \
	--volume "$(PWD)":/opt/workdir \
	--user `id -u`:`id -g` \
	python3_review_template \
	python3 analysis/status.py

combine_individual_search_results :
	docker run -ti \
	--volume "$(PWD)":/opt/workdir \
	--user `id -u`:`id -g` \
	python3_review_template \
	python3 analysis/combine_individual_search_results.py

backward_search :
	docker run -ti \
	--volume "$(PWD)":/opt/workdir \
	--user `id -u`:`id -g` \
	python3_review_template \
	python3 analysis/backward_search.py

cleanse_records :
	docker run -ti \
	--volume "$(PWD)":/opt/workdir \
	--user `id -u`:`id -g` \
	python3_review_template \
	python3 analysis/cleanse_records.py

pre_merging_quality_check :
	docker run -ti \
	--volume "$(PWD)":/opt/workdir \
	--user `id -u`:`id -g` \
	python3_review_template \
	python3 analysis/pre_merging_quality_check.py

extract_manual_pre_merging_edits :
	docker run -ti \
	--volume "$(PWD)":/opt/workdir \
	--user `id -u`:`id -g` \
	python3_review_template \
	python3 analysis/extract_manual_pre_merging_edits.py

screen_sheet :
	docker run -ti \
	--volume "$(PWD)":/opt/workdir \
	--user `id -u`:`id -g` \
	python3_review_template \
	python3 analysis/screen_sheet.py

screen_1 :
	docker run -ti \
	--volume "$(PWD)":/opt/workdir \
	--user `id -u`:`id -g` \
	python3_review_template \
	python3 analysis/screen_1.py

screen_2 :
	docker run -ti \
	--volume "$(PWD)":/opt/workdir \
	--user `id -u`:`id -g` \
	python3_review_template \
	python3 analysis/screen_2.py

data_sheet :
	docker run -ti \
	--volume "$(PWD)":/opt/workdir \
	--user `id -u`:`id -g` \
	python3_review_template \
	python3 analysis/data_sheet.py
