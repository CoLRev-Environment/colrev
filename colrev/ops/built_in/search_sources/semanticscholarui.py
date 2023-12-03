import inquirer


class SemanticScholarUI:

    """Implements the User Interface for the SemanticScholar API Search within colrev"""

    searchSubject = ""
    searchParams = {}


    def mainUI(self) -> None:

        """Display the main Menu and choose the search type"""

        print("\nWelcome to SemanticScholar! \n\n")
        mainMsg = "Please choose one of the options below: "
        mainOptions = ["Search for paper", "Search for author", "Keyword search"]

        fwdValue = self.chooseOption(msg=mainMsg, options=mainOptions)

        if fwdValue == "Search for paper":
            self.searchSubject = "paper"
            self.paperUI()
        
        elif fwdValue == "Search for author":
            self.searchSubject = "author"
            self.authorUI()

        elif fwdValue == "Keyword search":
            self.searchSubject = "keyword"
            self.keywordUI()


    def paperUI(self) -> None:
        
        """Ask user to enter search parameters for distinctive paper search"""

        paperIDList = []
        queryList = []
        morePapers = True

        while morePapers:

            pMsg = "How would you like to search for the paper?"
            pOptions = ["S2PaperId", "CorpusId", "DOI", "ArXivId", "MAG", "ACL", "PMID", "PMCID", "URL", "Search by title"]

            param = self.chooseOption(msg=pMsg, options=pOptions)

            if param in pOptions and not (param == "Search by title"):
                paramValue = self.enterText(msg="Please enter the chosen ID in the right format: ")

                if len(paperIDList) == 0:
                    self.searchParams["paper_id"] = paramValue
                    paperIDList.append(paramValue)
                elif len(paperIDList) == 1:
                    paperIDList.append(paramValue)
                    del self.searchParams["paper_id"]
                    self.searchParams["paper_ids"] = paperIDList
                else:
                    paperIDList.append(paramValue)
                    self.searchParams["paper_ids"] = paperIDList

            elif param == "Search by title":
                paramValue = self.enterText(msg="Please enter the title of the paper: ")
                
                if len(queryList) == 0:
                    self.searchParams["query"] = paramValue
                    queryList.append(paramValue)
                elif len(queryList) == 1:
                    queryList.append(paramValue)
                    del self.searchParams["query"]
                    self.searchParams["query_list"] = queryList
                else:
                    queryList.append(paramValue)
                    self.searchParams["query_list"] = queryList

            if self.chooseOption(msg="Would you like to search for another paper?", options=["YES", "NO"]) == "NO":
                morePapers = False

        #asking for specific fields not implemented: Import question!!
                
        print("\nDoing magic...")
        

    def authorUI(self) -> None:

        """Ask user to enter search parameters for distinctive author search"""

        authorIDList = []
        queryList = []
        moreAuthors = True

        while moreAuthors:

            aMsg = "How would you like to search for the author?"
            aOptions = ["S2AuthorId", "Search by name"]

            param = self.chooseOption(msg=aMsg, options=aOptions)

            if param == "S2AuthorId":
                paramValue = self.enterText(msg="Please enter the author ID in the right format: ")
                if len(authorIDList) == 0:
                    self.searchParams["author_id"] = paramValue
                    authorIDList.append(paramValue)
                elif len(authorIDList) == 1:
                    authorIDList.append(paramValue)
                    del self.searchParams["author_id"]
                    self.searchParams["author_ids"] = authorIDList
                else:
                    authorIDList.append(paramValue)
                    self.searchParams["author_ids"] = authorIDList


            elif param == "Search by name":
                paramValue = self.enterText(msg="Please enter the name of the author: ")
                if len(queryList) == 0:
                    self.searchParams["query"] = paramValue
                    queryList.append(paramValue)
                elif len(queryList) == 1:
                    queryList.append(paramValue)
                    del self.searchParams["query"]
                    self.searchParams["querylist"] = queryList
                else:
                    queryList.append(paramValue)
                    self.searchParams["querylist"] = queryList
            
            fwd = self.chooseOption(msg="Would you like to search for another author?", options=["YES", "NO"])
            
            if fwd == "NO":
                moreAuthors = False
                
        #asking for specific fields not implemented: Import question!!
        
        print("\nDoing magic...")

    def keywordUI(self) -> None:

        """Ask user to enter Searchstring and limitations for Keyword search"""
        
        query = self.enterText(msg="Please enter the Query for your Keyword search: ")
        self.searchParams["query"] = query

        year = self.enterText(msg="Please enter the yearspan for your Keyword search. You can press Enter if you don't wish to specify a yearspan: ")
        self.searchParams["year"] = year

        publication_types = self.enterText(msg="Please enter the publication types you'd like to include in your Keyword search. Separate multiple types by comma. "+ 
                                           "You can press Enter if you don't wish to restrict your query to certain publication types: ")
        self.searchParams["publication_types"] = publication_types.split(",")

        venue = self.enterText(msg="Please enter the venues for your Keyword search. Separate multiple venues by comma. You can press Enter if you don't wish to specify any venues: ")
        self.searchParams["venue"] = venue.split(",")

        fields_of_study = self.enterText(msg="Please enter the fields of study for your Keyword search. Separate multiple study fields by comma."+ 
                                            "You can press Enter if you don't wish to specify any study fields: ")
        self.searchParams["fields_of_study"] = fields_of_study.split(",")

        open_access = self.chooseOption(msg="If available, would you like to include a direct link to the respective pdf file of each paper to the results?", options=["YES", "NO"])
        if open_access == "YES":
            self.searchParams["open_access_pdf"] = True
        else:
            self.searchParams["open_access_pdf"] = False

        limit = self.enterText(msg="How many search results should the query include? Please enter a number between 1 and 1000: ")
        self.searchParams["limit"] = limit.format(int)

        #asking for specific fields not implemented: Import question!!

        print("\nDoing magic...")


    def chooseOption(self,
                     *,
                     msg: str,
                     options,
                     ) -> str:
        
        """Method to display a question with single choice answers to the console using inquirer"""

        question = [inquirer.List(name="Choice",
                                  message=msg,
                                  choices=["%s" % i for i in options],
                                  carousel=False,
                                  ),
                    ]
        choice = inquirer.prompt(questions=question)

        return choice.get("Choice")
    
    def enterText(self,
                  *,
                  msg: str,
                  ) -> str:
        
        """Method to display a question with free text entry answer to the console using inquirer"""

        question = [inquirer.Text(name="Entry", message=msg,)]
        choice = inquirer.prompt(questions=question)

        return choice.get("Entry")
    

# test
test = SemanticScholarUI()
test.mainUI()
print("\nSearch Subject: ", test.searchSubject)
for key,value in test.searchParams.items():
    print("Search parameter: ", key, ":", value)




