#! /usr/bin/env python
import asyncio
import datetime
import logging
import queue
import threading
import time
from collections import deque

from watchdog.events import LoggingEventHandler
from watchdog.observers import Observer

import colrev_core.cli
import colrev_core.cli_colors as colors
import colrev_core.environment
import colrev_core.status


class Event(LoggingEventHandler):
    def __init__(self, *, SERVICE):
        self.SERVICE = SERVICE
        self.logger = logging.getLogger()

    def on_modified(self, *, event):
        if event.is_directory:
            return
        if any(x in event.src_path for x in [".git/", "report.log", ".goutputstream"]):
            return

        time_since_last_change = (
            datetime.datetime.now() - self.SERVICE.last_file_change_date
        ).total_seconds()
        if (
            event.src_path == self.SERVICE.last_file_changed
            and time_since_last_change < 1
        ):
            pass
        else:
            self.SERVICE.logger.info("Detected change in file: " + event.src_path)

        self.SERVICE.last_file_change_date = datetime.datetime.now()
        self.SERVICE.last_file_changed = event.src_path

        stat = self.SERVICE.REVIEW_MANAGER.get_status_freq()
        instructions = self.SERVICE.STATUS.get_review_instructions(stat)

        for instruction in instructions:
            if "cmd" in instruction:
                cmd = instruction["cmd"]
                if "priority" in instruction:
                    # Note : colrev load can always be called but we are only interested
                    # in it if data in the search directory changes.
                    if "colrev load" == cmd and "search/" not in event.src_path:
                        return
                    self.SERVICE.q.put({"name": cmd, "cmd": cmd, "priority": "yes"})


class Service:
    def __init__(self, *, REVIEW_MANAGER):

        assert "realtime" == REVIEW_MANAGER.settings.project.review_type

        print("Starting realtime CoLRev service...")

        self.REVIEW_MANAGER = REVIEW_MANAGER

        self.previous_command = "none"
        self.last_file_changed = ""
        self.last_file_change_date = datetime.datetime.now()
        self.last_command_run_time = datetime.datetime.now()

        self.logger = self.__setup_service_logger(level=logging.INFO)

        # already start LocalIndex and Grobid (asynchronously)
        self.start_services()

        # setup queue
        self.q = queue.Queue()
        # Turn-on the worker thread.
        threading.Thread(target=self.worker, daemon=True).start()

        self.logger.info("Service alive")

        self.q.put({"name": "colrev search", "cmd": "colrev search", "priority": "yes"})

        # TODO : setup search feed (querying all 5-10 minutes?)

        # get initial review instructions and add to queue
        self.STATUS = colrev_core.status.Status(REVIEW_MANAGER=self.REVIEW_MANAGER)
        stat = self.REVIEW_MANAGER.get_status_freq()
        instructions = self.STATUS.get_review_instructions(stat=stat)
        for instruction in instructions:
            if "cmd" in instruction:
                cmd = instruction["cmd"]
                self.q.put({"name": cmd, "cmd": cmd})

        event_handler = Event(SERVICE=self)
        observer = Observer()
        observer.schedule(event_handler, self.REVIEW_MANAGER.path, recursive=True)
        observer.start()
        try:
            while observer.is_alive():
                observer.join(1)

        finally:
            observer.stop()
            observer.join()

        # Block until all tasks are done.
        self.q.join()

    def start_services(self):
        async def _start_grobid():
            GROBID_SERVICE = colrev_core.environment.GrobidService()
            GROBID_SERVICE.start()

        async def _start_index():
            colrev_core.environment.LocalIndex()

        asyncio.ensure_future(_start_grobid())
        asyncio.ensure_future(_start_index())

    # function to add commands to queue?

    def __setup_service_logger(self, *, level=logging.INFO) -> logging.Logger:
        service_logger = logging.getLogger("colrev_service")

        service_logger.setLevel(level)

        if service_logger.handlers:
            for handler in service_logger.handlers:
                service_logger.removeHandler(handler)

        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] CoLRev Service Bot: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler = logging.StreamHandler()
        handler.setFormatter(formatter)
        handler.setLevel(level)

        service_logger.addHandler(handler)
        service_logger.propagate = False

        return service_logger

    def worker(self):
        try:
            while True:

                # Ensure that tasks are unique and priority items
                self.q.queue = deque(
                    list(
                        {
                            v["cmd"]: v
                            for v in self.q.queue
                            if "priority" in v
                            and not any(
                                x in v.get("msg", "")
                                for x in [
                                    "in progress. Complete this process",
                                    "Import search results",
                                ]
                            )
                            and not v["cmd"] == self.previous_command
                        }.values()
                    )
                )
                if not self.REVIEW_MANAGER.paths["SEARCHDIR"].is_dir():
                    self.REVIEW_MANAGER.paths["SEARCHDIR"].mkdir()
                    self.logger.info("Created search dir")

                if 0 == self.q.qsize():
                    time.sleep(1)
                    # self.previous_command = "none"
                    continue

                print()
                self.logger.info(
                    f'Queue: {", ".join(q_item["cmd"] for q_item in self.q.queue)}'
                )

                item = self.q.get()
                item["cmd"] = item["cmd"].replace("_", "-")

                self.previous_command = item["cmd"]

                print()
                if "colrev search" == item["cmd"]:
                    from colrev_core.search import Search

                    SEARCH = Search(REVIEW_MANAGER=self.REVIEW_MANAGER)
                    SEARCH.main(selection_str=None)

                elif "colrev load" == item["cmd"]:
                    from colrev_core.load import Loader

                    if len(list(self.REVIEW_MANAGER.paths["SEARCHDIR"].glob("*"))) > 0:

                        self.logger.info(f"Running {item['name']}")

                        LOADER = Loader(REVIEW_MANAGER=self.REVIEW_MANAGER)
                        print()
                        LOADER.check_update_sources()
                        LOADER.main(keep_ids=False, combine_commits=False)
                    else:
                        self.q.task_done()
                        continue

                elif "colrev prep" == item["cmd"]:
                    from colrev_core.prep import Preparation

                    self.logger.info(f"Running {item['name']}")
                    PREPARATION = Preparation(REVIEW_MANAGER=self.REVIEW_MANAGER)
                    PREPARATION.main()
                elif "colrev dedupe" == item["cmd"]:
                    from colrev_core.dedupe import Dedupe

                    self.logger.info(f"Running {item['name']}")

                    # Note : settings should be
                    # simple_dedupe
                    # merge_threshold=0.5,
                    # partition_threshold=0.8,
                    DEDUPE = Dedupe(REVIEW_MANAGER=self.REVIEW_MANAGER)
                    DEDUPE.main()

                elif "colrev prescreen" == item["cmd"]:
                    from colrev_core.prescreen import Prescreen

                    self.logger.info(f"Running {item['name']}")
                    PRESCREEN = Prescreen(REVIEW_MANAGER=self.REVIEW_MANAGER)
                    PRESCREEN.include_all_in_prescreen()

                elif "colrev pdf-get" == item["cmd"]:
                    from colrev_core.pdf_get import PDF_Retrieval

                    self.logger.info(f"Running {item['name']}")
                    PDF_RETRIEVAL = PDF_Retrieval(REVIEW_MANAGER=self.REVIEW_MANAGER)
                    PDF_RETRIEVAL.main()

                elif "colrev pdf-prep" == item["cmd"]:
                    from colrev_core.pdf_prep import PDF_Preparation

                    # TODO : this may be solved more elegantly,
                    # but we need colrev to link existing pdfs (file field)
                    from colrev_core.pdf_get import PDF_Retrieval

                    self.logger.info(f"Running {item['name']}")
                    PDF_RETRIEVAL = PDF_Retrieval(REVIEW_MANAGER=self.REVIEW_MANAGER)
                    PDF_RETRIEVAL.main()

                    PDF_PREPARATION = PDF_Preparation(
                        REVIEW_MANAGER=self.REVIEW_MANAGER, reprocess=False
                    )
                    PDF_PREPARATION.main()

                elif "colrev pdf-prep" == item["cmd"]:
                    from colrev_core.pdf_prep import PDF_Preparation

                    self.logger.info(f"Running {item['name']}")
                    PDF_PREPARATION = PDF_Preparation(
                        REVIEW_MANAGER=self.REVIEW_MANAGER, reprocess=False
                    )
                    PDF_PREPARATION.main()

                elif "colrev screen" == item["cmd"]:
                    from colrev_core.screen import Screen

                    self.logger.info(f"Running {item['name']}")
                    SCREEN = Screen(REVIEW_MANAGER=self.REVIEW_MANAGER)
                    SCREEN.include_all_in_screen()

                elif "colrev data" == item["cmd"]:
                    from colrev_core.data import Data

                    self.logger.info(f"Running {item['name']}")
                    DATA = Data(self.REVIEW_MANAGER)
                    DATA.main()
                    input("Waiting for synthesis (press enter to continue)")

                elif item["cmd"] in [
                    '"colrev man-prep"',
                    "colrev pdf-get-man",
                    "colrev pdf-prep-man",
                ]:
                    print(
                        f"As a next step, please complete {item['name']}"
                        " manually (or press Enter to skip)"
                    )
                    self.q.task_done()
                    continue
                else:
                    if item["name"] not in ["git add records.bib"]:
                        input(f'Complete task: {item["name"]}')
                    self.q.task_done()

                    continue

                self.logger.info(f"{colors.GREEN}Completed {item['name']}{colors.END}")

                if 0 == self.q.qsize():
                    time.sleep(1)
                    continue
                self.q.task_done()
        except KeyboardInterrupt:
            print("Shutting down service")


if __name__ == "__main__":
    pass
