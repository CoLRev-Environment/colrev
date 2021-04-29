.PHONY : run status search cleanse_records screen data

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

cleanse_records :
	$(MAKE) -C analysis cleanse_records

screen :
	$(MAKE) -C analysis screen

data :
	$(MAKE) -C analysis data
