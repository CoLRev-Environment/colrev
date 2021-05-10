.PHONY : run status search backward_search cleanse_records screen data

help :
	@echo "Usage: make [command]"
	@echo "    help"
	@echo "        Show this help description"
	@echo "    run"
	@echo "        Run analyses of the complete repository"


sample_profile :
	docker run -ti \
	--volume "$(PWD)":/home/rstudio \
	--user `id -u`:`id -g` \
	review_template_r \
	Rscript -e "source('analysis/R/analyses.R')"
