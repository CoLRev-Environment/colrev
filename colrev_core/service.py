#! /usr/bin/env python
import datetime
import logging
import queue
import threading
import time

from watchdog.events import LoggingEventHandler
from watchdog.observers import Observer

from colrev_core.status import Status


class Event(LoggingEventHandler):
    def __init__(self, SERVICE):
        self.SERVICE = SERVICE
        self.logger = logging.getLogger()

    def on_modified(self, event):
        if event.is_directory:
            return
        if any(x in event.src_path for x in [".git/", "report.log", ".goutputstream"]):
            return

        time_since_last_change = (
            datetime.datetime.now() - self.SERVICE.last_file_change_date
        ).total_seconds()
        if (
            event.src_path == self.SERVICE.last_file_changed
            and time_since_last_change < 5
        ):
            return

        self.SERVICE.last_file_change_date = datetime.datetime.now()
        self.SERVICE.last_file_changed = event.src_path

        # print(event.event_type)
        print("Saved " + event.src_path)

        stat = self.SERVICE.STATUS.get_status_freq()
        instructions = self.SERVICE.STATUS.get_review_instructions(stat)
        for instruction in instructions:
            if "cmd" in instruction:
                cmd = instruction["cmd"]
                self.SERVICE.q.put({"name": cmd, "cmd": cmd})


class Service:
    def __init__(self, REVIEW_MANAGER):

        assert "realtime" == REVIEW_MANAGER.settings.project.review_type

        print("Starting realtime CoLRev service")

        self.REVIEW_MANAGER = REVIEW_MANAGER

        self.previous_command = "none"
        self.last_file_changed = ""
        self.last_file_change_date = datetime.datetime.now()

        # setup queue
        self.q = queue.Queue()
        # Turn-on the worker thread.
        threading.Thread(target=self.worker, daemon=True).start()

        # Send thirty task requests to the worker.
        # for item in range(3):
        #     self.q.put(item)
        # time.sleep(20)
        # self.q.put(19)

        # get initial review instructions and add to queue
        self.STATUS = Status(self.REVIEW_MANAGER)
        stat = self.STATUS.get_status_freq()
        instructions = self.STATUS.get_review_instructions(stat)
        for instruction in instructions:
            if "cmd" in instruction:
                cmd = instruction["cmd"]
                self.q.put({"name": cmd, "cmd": cmd})

        # logging.basicConfig(level=logging.INFO,
        #                         format='%(asctime)s - %(message)s',
        #                         datefmt='%Y-%m-%d %H:%M:%S')
        event_handler = Event(self)
        observer = Observer()
        observer.schedule(event_handler, self.REVIEW_MANAGER.path, recursive=True)
        observer.start()
        try:
            while observer.isAlive():
                observer.join(1)

        finally:
            observer.stop()
            observer.join()

        # setup watchdog, which adds to queue

        # Block until all tasks are done.
        self.q.join()
        pass

    # function to add commands to queue?

    def worker(self):
        try:
            while True:
                if 0 == self.q.qsize():
                    time.sleep(1)
                    continue
                item = self.q.get()
                if item["cmd"] == self.previous_command:
                    continue
                else:
                    self.previous_command = item["cmd"]
                print(f"Working on {item}")

                if "colrev load" == item["cmd"]:
                    from colrev_core.load import Loader
                    from colrev.cli import check_update_sources

                    LOADER = Loader(self.REVIEW_MANAGER)
                    check_update_sources(LOADER)
                    LOADER.main(keep_ids=False, combine_commits=False)
                elif "colrev prep" == item["cmd"]:
                    from colrev_core.prep import Preparation

                    PREPARATION = Preparation(self.REVIEW_MANAGER)
                    PREPARATION.main()
                elif "colrev dedupe" == item["cmd"]:
                    from colrev_core.dedupe import Dedupe
                    from colrev.cli import run_dedupe

                    DEDUPE = Dedupe(self.REVIEW_MANAGER)
                    # TODO : check thresholds
                    run_dedupe(
                        DEDUPE,
                        retrain=False,
                        merge_threshold=0.5,
                        partition_threshold=0.8,
                    )

                elif "colrev prescreen" == item["cmd"]:
                    from colrev_core.prescreen import Prescreen

                    PRESCREEN = Prescreen(self.REVIEW_MANAGER)
                    PRESCREEN.include_all_in_prescreen()

                elif "colrev pdf-get" == item["cmd"]:
                    from colrev_core.pdf_get import PDF_Retrieval

                    PDF_RETRIEVAL = PDF_Retrieval(self.REVIEW_MANAGER)
                    PDF_RETRIEVAL.main()

                elif "colrev pdf-prep" == item["cmd"]:
                    from colrev_core.pdf_prep import PDF_Preparation

                    # TODO : this may be solved more elegantly,
                    # but we need colrev to link existing pdfs (file field)
                    from colrev_core.pdf_get import PDF_Retrieval

                    PDF_RETRIEVAL = PDF_Retrieval(self.REVIEW_MANAGER)
                    PDF_RETRIEVAL.main()

                    PDF_PREPARATION = PDF_Preparation(
                        self.REVIEW_MANAGER, reprocess=False
                    )
                    PDF_PREPARATION.main()

                elif "colrev pdf-prep" == item["cmd"]:
                    from colrev_core.pdf_prep import PDF_Preparation

                    PDF_PREPARATION = PDF_Preparation(
                        self.REVIEW_MANAGER, reprocess=False
                    )
                    PDF_PREPARATION.main()

                elif "colrev screen" == item["cmd"]:
                    from colrev_core.screen import Screen

                    SCREEN = Screen(self.REVIEW_MANAGER)
                    SCREEN.include_all_in_screen()

                elif "colrev data" == item["cmd"]:
                    from colrev_core.data import Data

                    DATA = Data(self.REVIEW_MANAGER)
                    DATA.main()

                elif item["cmd"] in [
                    '"colrev man-prep"',
                    "colrev pdf-get-man",
                    "colrev pdf-prep-man",
                ]:
                    print(f"As a next step, please complete {item['name']} manually")

                # print(f"Finished {item}")
                if 0 == self.q.qsize():
                    time.sleep(1)
                    continue
                self.q.task_done()
        except KeyboardInterrupt:
            print("Shutting down service")
            pass


if __name__ == "__main__":
    pass
