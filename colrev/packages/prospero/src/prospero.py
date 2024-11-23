#! /usr/bin/env python
"""SearchSource: Prospero"""
import zope.interface
import colrev.package_manager.interfaces
import colrev.package_manager.package_manager
import colrev.package_manager.package_settings
from colrev.constants import SearchType
from colrev.constants import SearchSourceHeuristicStatus
from pydantic import Field

@zope.interface.implementer(colrev.package_manager.interfaces.SearchSourceInterface)
class ProsperoSearchSource:
    """Prospero"""

    settings_class = colrev.package_manager.package_settings.DefaultSourceSettings
    #endpoint = "colrev.prospero"
    
    source_identifier = "url"
    #search_types = [SearchType.DB]

    #ci_supported: bool = Field(default=False)
    #heuristic_status = SearchSourceHeuristicStatus.supported
    #heuristic status likely supported, how to confirm?

    db_url = "https://www.crd.york.ac.uk/prospero/"
