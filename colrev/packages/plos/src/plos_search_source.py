#! /usr/bin/env python
"""SearchSourceInterface: PlosSearchSource"""

from zope.interface import implementer
from colrev.package_manager.interfaces import SearchSourceInterface
import colrev.package_manager.package_settings
import colrev.process.operation

@implementer(SearchSourceInterface)
class PlosSearchSource:
    settings_class = '' #TODO
    source_identifier = '' #TODO
    search_types = '' #TODO
    heuristic_status = '' #TODO




    def __init__(
        self,
        *,
        source_operation: colrev.process.operation.Operation,
        settings: typing.Optional[dict] = None,
    ) -> None:
      pass # TODO

    def heuristic(self, filename, data):
      """Heuristic to identify to which SearchSource a search file belongs (for DB searches)"""
      # TODO

    def add_endpoint(self, operation, params):
      """Add the SearchSource as an endpoint based on a query (passed to colrev search -a)
        params:
        - search_file="..." to add a DB search
        """
      # TODO

    def search(self, rerun):
      """Run a search of the SearchSource"""
      # TODO

    def prep_link_md(self, prep_operation, record, save_feed=True, timeout=10):
      """Retrieve masterdata from the SearchSource"""
      # TODO

    def load(self, load_operation):
      """Load records from the SearchSource (and convert to .bib)"""
      # TODO

    def prepare(self, record, source):
      """Run the custom source-prep operation"""
      # TODO

