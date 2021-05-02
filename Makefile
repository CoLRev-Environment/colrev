.PHONY : run status search backward_search cleanse_records screen data

help :
	@echo "Usage: make [command]"
	@echo "    help"
	@echo "        Show this help description"
	@echo "    run"
	@echo "        Run analyses of the complete repository"

run :
	$(MAKE) -C analysis run

status :
	$(MAKE) -C analysis status

search :
	$(MAKE) -C analysis search

backward_search :
	$(MAKE) -C analysis backward_search

cleanse_records :
	$(MAKE) -C analysis cleanse_records

pre_merging_quality_check :
	$(MAKE) -C analysis pre_merging_quality_check

extract_manual_pre_merging_edits :
	$(MAKE) -C analysis extract_manual_pre_merging_edits

screen :
	$(MAKE) -C analysis screen

screen_1 :
	$(MAKE) -C analysis screen_1

screen_2 :
	$(MAKE) -C analysis screen_2

data :
	$(MAKE) -C analysis data
