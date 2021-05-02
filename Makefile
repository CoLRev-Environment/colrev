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

combine_individual_search_results :
	$(MAKE) -C analysis combine_individual_search_results

backward_search :
	$(MAKE) -C analysis backward_search

cleanse_records :
	$(MAKE) -C analysis cleanse_records

pre_merging_quality_check :
	$(MAKE) -C analysis pre_merging_quality_check

extract_manual_pre_merging_edits :
	$(MAKE) -C analysis extract_manual_pre_merging_edits

screen_sheet :
	$(MAKE) -C analysis screen_sheet

screen_1 :
	$(MAKE) -C analysis screen_1

screen_2 :
	$(MAKE) -C analysis screen_2

data_sheet :
	$(MAKE) -C analysis data_sheet
