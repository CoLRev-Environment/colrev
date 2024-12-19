#! /usr/bin/env python
"""SearchSource: plos"""
import colrev.loader
import colrev.loader.load_utils
import colrev.ops
import colrev.ops.prep
import colrev.ops.search
import colrev.ops.search_api_feed
#from future import annotations

import datetime
import typing
from multiprocessing import Lock
from pathlib import Path
import colrev.settings

import colrev.process
import colrev.process.operation
import inquirer
import requests
import zope.interface
from pydantic import Field

import colrev.env.language_service
import colrev.exceptions as colrev_exceptions
import colrev.package_manager.interfaces
import colrev.package_manager.package_settings
import colrev.packages.doi_org.src.doi_org as doi_connector
import colrev.record.record
import colrev.record.record_prep
import colrev.record.record_similarity
from colrev.constants import Fields
from colrev.constants import FieldValues
from colrev.constants import RecordState
from colrev.constants import SearchSourceHeuristicStatus
from colrev.constants import SearchType
from colrev.packages.plos.src import plos_api
import logging



@zope.interface.implementer(colrev.package_manager.interfaces.SearchSourceInterface)
class PlosSearchSource:
    
    endpoint = "colrev.plos"
    settings_class = colrev.package_manager.package_settings.DefaultSourceSettings
    source_identifier = Fields.DOI
    search_types = [ SearchType.API, SearchType.TOC, SearchType.MD]
    heuristic_status = SearchSourceHeuristicStatus.oni

    _api_url = "http://api.plos.org/"



    # Configuración básica del logger
    logging.basicConfig(level=logging.DEBUG,  # Nivel de logging
                    format='%(asctime)s - %(levelname)s - %(message)s')  # Formato del log

    def __init__(
        self,
        *,
        source_operation: colrev.process.operation.Operation,
        settings: typing.Optional[dict] = None,
    ) -> None:
      self.review_manager = source_operation.review_manager
      self.search_source = self._get_search_source(settings)
      self.plos_lock = Lock()
      self.language_service = colrev.env.language_service.LanguageService()

      self.api = plos_api.PlosAPI(params=self.search_source.search_parameters)
   #Function to define the search source. 
    #   If setting exist, use that settings
    #   If not, return the .bib
    #   If it does not exist, create new one (.bib) 
    def _get_search_source(
        self, settings: typing.Optional[dict]
    ) -> colrev.settings.SearchSource:
        if settings:
            # plos as a search_source
            return self.settings_class(**settings)

        # plos as an md-prep source
        plos_md_filename = Path("data/search/md_plos.bib")
        plos_md_source_l = [
            s
            for s in self.review_manager.settings.sources
            if s.filename == plos_md_filename
        ]
        if plos_md_source_l:
            return plos_md_source_l[0]

        return colrev.settings.SearchSource(
            endpoint="colrev.plos",
            filename=plos_md_filename,
            search_type=SearchType.MD,
            search_parameters={},
            comment="",
        )


    def heuristic(self, filename, data):
      """Heuristic to identify to which SearchSource a search file belongs (for DB searches)"""
      # TODO

    @classmethod
    def _select_search_type( 
       self, operation: colrev.ops.search.Search, params_dict: dict
    ) -> SearchType:
        if "query" in params_dict:
          search_type = SearchType.API
        elif Fields.URL in params_dict:
          search_type = SearchType.API
        else:
            search_type = operation.select_search_type(
                search_types=self.search_types, params=params_dict
            )


        return search_type


    @classmethod
    def add_endpoint(
          self,
          operation: colrev.ops.search.Search,
          params: str,
    ) -> colrev.settings.SearchSource:
      """Add the SearchSource as an endpoint based on a query (passed to colrev search -a)
        params:
        - search_file="..." to add a DB search
        """
      
      search_type = self._select_search_type(operation, params)
      if search_type == SearchType.API:
         if len(params) == 0:
            search_source = operation.create_api_source(endpoint=self.endpoint)

            search_source.search_parameters["url"] = (
               self._api_url + "search?" +
               "q="
               + search_source.search_parameters.pop("query", "").replace(" ", "+")
               )
            search_source.search_parameters["version"] = "0.1.0"

            operation.add_source_and_search(search_source)
      
            return search_source
         else:
            if Fields.URL in params:
               query = {"url": params[Fields.URL]}
            else:
               query = params
            
            filename = operation.get_unique_filename(file_path_string="plos")
            
            search_source = colrev.settings.SearchSource(
                    endpoint="colrev.plos",
                    filename=filename,
                    search_type=SearchType.API,
                    search_parameters=query,
                    comment="",
                )
            
            operation.add_source_and_search(search_source)
      
            return search_source

      else:
        raise NotImplementedError   
     
    
    def _prep_plos_record(
          self, 
          *, 
          record: colrev.record.record.Record, 
          prep_main_record: bool = True, 
          plos_source: str = "", 
    ) -> None:
        
        if Fields.LANGUAGE in record.data:
          try:
              self.language_service.unify_to_iso_639_3_language_codes(record=record)
          except colrev_exceptions.InvalidLanguageCodeException:
              del record.data[Fields.LANGUAGE]   
        #input("after language")
        #input(record)
        doi_connector.DOIConnector.get_link_from_doi(
            review_manager=self.review_manager,
            record=record,
        )        
        #input("after get link")
        #input(record)

        #REFERENCES?
        if (
            self.review_manager.settings.is_curated_masterdata_repo()
        ) and Fields.CITED_BY in record.data:
            del record.data[Fields.CITED_BY] 

        #input("after cited_by")
        #
        #input(record)

        if not prep_main_record:
           return
        
        #retracted??
        
    def _restore_url(
            self, 
            *,
            record: colrev.record.record.Record,
            feed: colrev.ops.search_api_feed.SearchAPIFeed
        ) -> None:
        "Restore the url from the feed if it exist"

        prev_record = feed.get_prev_feed_record(record)
        prev_url = prev_record.data.get(Fields.URL, None)

        if prev_url is None:
            return
        record.data[Fields.URL] = prev_url

    def _run_api_search( 
          self, 
          *, 
          plos_feed: colrev.ops.search_api_feed.SearchAPIFeed,
          rerun: bool,
    ) -> None:
        self.api.rerun = rerun
        self.api.last_updated = plos_feed.get_last_updated()

        num_records = self.api.get_len_total()
        self.review_manager.logger.info(f"Total: {num_records:,} records")

        #It retrieves only new records added since the last sync, avoiding a full download       if not rerun:
          #REPASR POR EL FORMATO DE LA FECHA
        if not rerun:
            self.review_manager.logger.info(
                  f"Retrieve papers indexed since {self.api.last_updated.split('T', maxsplit=1)[0]}"
            )
            num_records = self.api.get_len()
        
        self.review_manager.logger.info(f"Retrieve {num_records:,} records")

        estimated_time = num_records * 0.5
        estimated_time_formatted = str(datetime.timedelta(seconds=int(estimated_time)))
        self.review_manager.logger.info(f"Estimated time: {estimated_time_formatted}")

        try:
            i = 0 
            for record in self.api.get_records():
                #input("item in _run_api_search after processing it")
                #input(record)
                try:
                    if self._scope_excluded(record.data):
                        continue
                      
                    #input("after de exclude the item in run_api")
                    #input(record)

                    self._prep_plos_record(
                        record = record, prep_main_record = False
                    )
                    #input("after de prepare the item in run_api")
                    #input(record)

                    #input("Before the restore and update")
                    #input(self)
                    #input(plos_feed)
                    self._restore_url(record=record, feed=plos_feed)

                    plos_feed.add_update_record(retrieved_record=record)

                    #input("After restore and update")
                    #input(self)
                    #input(plos_feed)

              
                except colrev_exceptions.NotFeedIdentifiableException:
                  pass
        except RuntimeError as e:
          print(e)

        plos_feed.save()

    def _scope_excluded(self, retrieved_record_dict: dict) -> bool:

      if (
          "scope" not in self.search_source.search_parameters
          or "years" not in self.search_source.search_parameters["scope"]
      ):
          return False

      year_from, year_to = self.search_source.search_parameters["scope"][
          "years"
      ].split("-")
      
      if not retrieved_record_dict.get(Fields.YEAR, -1000).isdigit():
          return True

      if (
          int(year_from)
          < int(retrieved_record_dict.get(Fields.YEAR, -1000))
          < int(year_to)
      ):
          return False
      return True

    def _validate_source(self) -> None:
        source = self.search_source

        if source.search_type not in self.search_types:
            raise colrev_exceptions.InvalidQueryException(
              f"Plos search_type should be in {self.search_types}"
            )

        if source.search_type == SearchType.API:
          self._validate_api_params()


        self.review_manager.logger.debug(f"SearchSource {source.filename} validated")
       
    def _validate_api_params(self):
        source = self.search_source

       

    def search(self, rerun: bool) -> None:
        """Run a search of the SearchSource"""
        self._validate_source()
        #Create the Object SearchAPIFeed which mange the search on the API
    
        plos_feed = self.search_source.get_api_feed(
              review_manager=self.review_manager,
              source_identifier=self.source_identifier,
              update_only=(not rerun),
        )

        
        if self.search_source.search_type in [
            SearchType.API,
            SearchType.TOC,
        ]:
            
            self._run_api_search(
                plos_feed=plos_feed,
                rerun=rerun,
            )

        if self.search_source.search_type == SearchType.API:
          pass

        elif self.search_source.search_type == SearchType.MD:
          pass
        else:
          raise NotImplementedError


    def _get_masterdata_record(
          self,
          prep_operation: colrev.ops.prep.Prep,
          record: colrev.record.record.Record,
          save_feed: bool
    ) -> colrev.record.record.Record:
        try:
            try:
                retrieved_record = self.api.query_doi(doi=record.data[Field.DOI])
            except (colrev_exceptions.RecordNotFoundInPrepSourceException, KeyError):
                
                retrieved_records = self.api.plos_query(
                record_input=record,
                jour_vol_iss_list=False
                )
                retrieved_record = retrieved_records.pop()

                retries = 0
                while(
                   not retrieved_record
                   and retries < prep_operation.max_retries_on_error
                ):
                   retries += 1

                   retrieved_records = self.api.plos_query(
                      record_input=record,
                      jour_vol_iss_list=False
                   )
                   retrieved_record = retrieved_records.pop()
            
            if not colrev.record.record_similarity.matches(record, retrieved_record):
               return record
            
            try: 
               self.plos_lock.acquire(timeout=120) #Check in PLOS

               plos_feed = self.search_source.get_api_feed(
                  review_manager=self.review_manager,
                  source_identifier=self.source_identifier,
                  update_only=False,
                  prep_mode=True
               )

               plos_feed.add_update_record(retrieved_record)

               record.merge(
                  retrieved_record,
                  default_source=retrieved_record.data[Fields.ORIGIN][0]
               )

               self._prep_plos_record(
                  record=record,
                  default_source=retrieved_record.data[Fields.ORIGIN[0]]
               )

               if save_feed:
                  plos_feed.save()

            except colrev_exceptions.NotFeedIdentifiableException:
               pass
            finally:
                try:
                  self.plos_lock.release()
                except ValueError:
                  pass
               
            return record
        except(
           colrev_exceptions.ServiceNotAvailableException,
           OSError,
           IndexError,
           colrev_exceptions.RecordNotFoundInPrepSourceException,
           colrev_exceptions.RecordNotParsableException
        ) as exc:
           if prep_operation.review_manager.verbose_mode:
              print(exc)

        return record


    def prep_link_md(self, prep_operation, record, save_feed=True, timeout=10):
      """Retrieve masterdata from the SearchSource"""
      # TODO

    def load(self, load_operation):
      """Load records from the SearchSource (and convert to .bib)"""
      input("entro en el load")
      
      if self.search_source.filename.suffix == ".bib":
         input("Entro en el if")
         records = colrev.loader.load_utils.load(
            filename=self.search_source.filename,
            logger=self.review_manager.logger,
            unique_id_field="ID"
         )
         print(records)
         return records
      
      input("Fuera del if")
      raise NotImplementedError

    def prepare(self, record, source):
      """Run the custom source-prep operation"""
      # TODO

