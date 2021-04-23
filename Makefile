.PHONY : run

help :
	@echo "Usage: make [command]"
	@echo "    help"
	@echo "        Show this help description"
	@echo "    run"
	@echo "        Run analyses of the complete repository"

run :
	[ -f analysis/Makefile ] && $(MAKE) -C analysis run || true # Skip if no Makefile in analysis directory
