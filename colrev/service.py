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

import colrev.cli_colors as colors
import colrev.status


class Event(LoggingEventHandler):
    def __init__(self, *, service):
        super().__init__()
        self.service = service
        self.logger = logging.getLogger()

    def on_modified(self, event):
        if event.is_directory:
            return
        if any(x in event.src_path for x in [".git/", "report.log", ".goutputstream"]):
            return

        time_since_last_change = (
            datetime.datetime.now() - self.service.last_file_change_date
        ).total_seconds()
        if (
            event.src_path == self.service.last_file_changed
            and time_since_last_change < 1
        ):
            pass
        else:
            self.service.logger.info("Detected change in file: " + event.src_path)

        self.service.last_file_change_date = datetime.datetime.now()
        self.service.last_file_changed = event.src_path

        stat = self.service.review_manager.get_status_freq()
        instructions = self.service.STATUS.get_review_instructions(stat)

        for instruction in instructions:
            if "cmd" in instruction:
                cmd = instruction["cmd"]
                if "priority" in instruction:
                    # Note : colrev load can always be called but we are only interested
                    # in it if data in the search directory changes.
                    if "colrev load" == cmd and "search/" not in event.src_path:
                        return
                    self.service.q.put({"name": cmd, "cmd": cmd, "priority": "yes"})


class Service:
    def __init__(self, *, review_manager):

        assert "realtime" == review_manager.settings.project.review_type

        print("Starting realtime CoLRev service...")

        self.review_manager = review_manager

        self.previous_command = "none"
        self.last_file_changed = ""
        self.last_file_change_date = datetime.datetime.now()
        self.last_command_run_time = datetime.datetime.now()

        self.logger = self.__setup_service_logger(level=logging.INFO)

        # already start LocalIndex and Grobid (asynchronously)
        self.start_services()

        # setup queue
        self.service_queue = queue.Queue()
        # Turn-on the worker thread.
        threading.Thread(target=self.worker, daemon=True).start()

        self.logger.info("Service alive")

        self.service_queue.put(
            {"name": "colrev search", "cmd": "colrev search", "priority": "yes"}
        )

        # TODO : setup search feed (querying all 5-10 minutes?)

        # get initial review instructions and add to queue
        self.status = colrev.status.Status(review_manager=self.review_manager)
        stat = self.review_manager.get_status_freq()
        instructions = self.status.get_review_instructions(stat=stat)
        for instruction in instructions:
            if "cmd" in instruction:
                cmd = instruction["cmd"]
                self.service_queue.put({"name": cmd, "cmd": cmd})

        event_handler = Event(service=self)
        observer = Observer()
        observer.schedule(event_handler, self.review_manager.path, recursive=True)
        observer.start()
        try:
            while observer.is_alive():
                observer.join(1)

        finally:
            observer.stop()
            observer.join()

        # Block until all tasks are done.
        self.service_queue.join()

    def start_services(self):
        async def _start_grobid():
            grobid_service = self.review_manager.get_grobid_serivce()

            grobid_service.start()

        async def _start_index():
            _ = self.review_manager.get_local_index()

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
                self.service_queue.queue = deque(
                    list(
                        {
                            v["cmd"]: v
                            for v in self.service_queue.queue
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
                if not self.review_manager.paths["SEARCHDIR"].is_dir():
                    self.review_manager.paths["SEARCHDIR"].mkdir()
                    self.logger.info("Created search dir")

                if 0 == self.service_queue.qsize():
                    time.sleep(1)
                    # self.previous_command = "none"
                    continue

                print()
                self.logger.info(
                    f'Queue: {", ".join(q_item["cmd"] for q_item in self.service_queue.queue)}'
                )

                item = self.service_queue.get()
                item["cmd"] = item["cmd"].replace("_", "-")

                self.previous_command = item["cmd"]

                print()
                if "colrev search" == item["cmd"]:
                    from colrev.search import Search

                    search = Search(review_manager=self.review_manager)
                    search.main(selection_str=None)

                elif "colrev load" == item["cmd"]:
                    from colrev.load import Loader

                    if len(list(self.review_manager.paths["SEARCHDIR"].glob("*"))) > 0:

                        self.logger.info(f"Running {item['name']}")

                        loader = Loader(review_manager=self.review_manager)
                        print()
                        loader.check_update_sources()
                        loader.main(keep_ids=False, combine_commits=False)
                    else:
                        self.service_queue.task_done()
                        continue

                elif "colrev prep" == item["cmd"]:
                    from colrev.prep import Preparation

                    self.logger.info(f"Running {item['name']}")
                    preparation = Preparation(review_manager=self.review_manager)
                    preparation.main()
                elif "colrev dedupe" == item["cmd"]:
                    from colrev.dedupe import Dedupe

                    self.logger.info(f"Running {item['name']}")

                    # Note : settings should be
                    # simple_dedupe
                    # merge_threshold=0.5,
                    # partition_threshold=0.8,
                    dedupe = Dedupe(review_manager=self.review_manager)
                    dedupe.main()

                elif "colrev prescreen" == item["cmd"]:
                    from colrev.prescreen import Prescreen

                    self.logger.info(f"Running {item['name']}")
                    prescreen = Prescreen(review_manager=self.review_manager)
                    prescreen.include_all_in_prescreen()

                elif "colrev pdf-get" == item["cmd"]:
                    from colrev.pdf_get import PDFRetrieval

                    self.logger.info(f"Running {item['name']}")
                    pdf_retrieval = PDFRetrieval(review_manager=self.review_manager)
                    pdf_retrieval.main()

                elif "colrev pdf-prep" == item["cmd"]:
                    from colrev.pdf_prep import PDFPreparation

                    # TODO : this may be solved more elegantly,
                    # but we need colrev to link existing pdfs (file field)
                    from colrev.pdf_get import PDFRetrieval

                    self.logger.info(f"Running {item['name']}")
                    pdf_retrieval = PDFRetrieval(review_manager=self.review_manager)
                    pdf_retrieval.main()

                    pdf_preparation = PDFPreparation(
                        review_manager=self.review_manager, reprocess=False
                    )
                    pdf_preparation.main()

                elif "colrev pdf-prep" == item["cmd"]:
                    from colrev.pdf_prep import PDFPreparation

                    self.logger.info(f"Running {item['name']}")
                    pdf_preparation = PDFPreparation(
                        review_manager=self.review_manager, reprocess=False
                    )
                    pdf_preparation.main()

                elif "colrev screen" == item["cmd"]:
                    from colrev.screen import Screen

                    self.logger.info(f"Running {item['name']}")
                    screen = Screen(review_manager=self.review_manager)
                    screen.include_all_in_screen()

                elif "colrev data" == item["cmd"]:
                    from colrev.data import Data

                    self.logger.info(f"Running {item['name']}")
                    data = Data(self.review_manager)
                    data.main()
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
                    self.service_queue.task_done()
                    continue
                else:
                    if item["name"] not in ["git add records.bib"]:
                        input(f'Complete task: {item["name"]}')
                    self.service_queue.task_done()

                    continue

                self.logger.info(f"{colors.GREEN}Completed {item['name']}{colors.END}")

                if 0 == self.service_queue.qsize():
                    time.sleep(1)
                    continue
                self.service_queue.task_done()
        except KeyboardInterrupt:
            print("Shutting down service")


if __name__ == "__main__":
    pass
