.PHONY : run

help :
	@echo "Usage: make [command]"
	@echo "    help"
	@echo "        Show this help description"
	@echo "    run"
	@echo "        Run analyses of the complete repository"

run : gather create_screening_sheet create_data_extraction_sheet

gather :
	docker run -ti \
	--volume "$(PWD)":/opt/workdir \
	--user `id -u`:`id -g` \
	python3_review_template \
	python3 analysis/gather.py

create_screening_sheet :
	docker run -ti \
	--volume "$(PWD)":/opt/workdir \
	--user `id -u`:`id -g` \
	python3_review_template \
	python3 analysis/create_screen.py

create_data_extraction_sheet :
	docker run -ti \
	--volume "$(PWD)":/opt/workdir \
	--user `id -u`:`id -g` \
	python3_review_template \
	python3 analysis/create_data_extraction.py
