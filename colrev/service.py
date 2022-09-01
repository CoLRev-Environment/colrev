#! /usr/bin/env python
from __future__ import annotations

import asyncio
import datetime
import logging
import queue
import threading
import time
from collections import deque
from typing import TYPE_CHECKING

from watchdog.events import LoggingEventHandler
from watchdog.observers import Observer

import colrev.cli_colors as colors
import colrev.status

if TYPE_CHECKING:
    import colrev.review_manager.ReviewManager


class Event(LoggingEventHandler):
    service: Service

    def __init__(self, *, service: Service):
        super().__init__()
        self.service = service
        self.logger: logging.Logger = logging.getLogger()

    def on_modified(self, event) -> None:
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
            self.logger.info(f"Detected change in file: {event.src_path}")

        self.service.last_file_change_date = datetime.datetime.now()
        self.service.last_file_changed = event.src_path

        stat = self.service.review_manager.get_status_freq()
        status_operation = self.service.review_manager.get_status_operation()
        instructions = status_operation.get_review_instructions(stat=stat)

        for instruction in instructions:
            if "cmd" in instruction:
                cmd = instruction["cmd"]
                if "priority" in instruction:
                    # Note : colrev load can always be called but we are only interested
                    # in it if data in the search directory changes.
                    if "colrev load" == cmd and "search/" not in event.src_path:
                        return
                    self.service.service_queue.put(
                        {"name": cmd, "cmd": cmd, "priority": "yes"}
                    )


class Service:
    review_manager: colrev.review_manager.ReviewManager

    def __init__(self, *, review_manager: colrev.review_manager.ReviewManager) -> None:

        assert "realtime" == review_manager.settings.project.review_type

        print("Starting realtime CoLRev service...")

        self.review_manager = review_manager

        self.previous_command: str = "none"
        self.last_file_changed: str = ""
        self.last_file_change_date: datetime.datetime = datetime.datetime.now()
        self.last_command_run_time: datetime.datetime = datetime.datetime.now()

        self.logger = self.__setup_service_logger(level=logging.INFO)

        # already start LocalIndex and Grobid (asynchronously)
        self.start_services()

        # setup queue
        self.service_queue: queue.Queue = queue.Queue()
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

    def start_services(self) -> None:
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

    def worker(self) -> None:
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

                    search_operation = self.review_manager.get_search_operation()
                    search_operation.main(selection_str=None)

                elif "colrev load" == item["cmd"]:

                    if len(list(self.review_manager.paths["SEARCHDIR"].glob("*"))) > 0:

                        self.logger.info(f"Running {item['name']}")

                        load_operation = self.review_manager.get_load_operation()
                        print()
                        load_operation.check_update_sources()
                        load_operation.main(keep_ids=False, combine_commits=False)
                    else:
                        self.service_queue.task_done()
                        continue

                elif "colrev prep" == item["cmd"]:

                    self.logger.info(f"Running {item['name']}")
                    preparation_operation = self.review_manager.get_prep_operation()
                    preparation_operation.main()
                elif "colrev dedupe" == item["cmd"]:

                    self.logger.info(f"Running {item['name']}")

                    # Note : settings should be
                    # simple_dedupe
                    # merge_threshold=0.5,
                    # partition_threshold=0.8,
                    dedupe_operation = self.review_manager.get_dedupe_operation()
                    dedupe_operation.main()

                elif "colrev prescreen" == item["cmd"]:

                    self.logger.info(f"Running {item['name']}")
                    prescreen_operation = self.review_manager.get_prescreen_operation()
                    prescreen_operation.include_all_in_prescreen()

                elif "colrev pdf-get" == item["cmd"]:

                    self.logger.info(f"Running {item['name']}")
                    pdf_get_operation = self.review_manager.get_pdf_get_operation()
                    pdf_get_operation.main()

                elif "colrev pdf-prep" == item["cmd"]:

                    # TODO : this may be solved more elegantly,
                    # but we need colrev to link existing pdfs (file field)

                    self.logger.info(f"Running {item['name']}")
                    pdf_get_operation = self.review_manager.get_pdf_get_operation()
                    pdf_get_operation.main()

                    pdf_preparation_operation = (
                        self.review_manager.get_pdf_prep_operation()
                    )
                    pdf_preparation_operation.main()

                elif "colrev screen" == item["cmd"]:

                    self.logger.info(f"Running {item['name']}")
                    screen_operation = self.review_manager.get_screen_operation()
                    screen_operation.include_all_in_screen()

                elif "colrev data" == item["cmd"]:

                    self.logger.info(f"Running {item['name']}")
                    data_operation = self.review_manager.get_data_operation()
                    data_operation.main()
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
