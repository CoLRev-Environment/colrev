import inquirer


class Semanticscholar_ui():

    '''Implements the User Interface for the SemanticScholar API Search within colrev'''

    searchSubject: str
    searchParams: dict

    #def __init__(self):
    '''__init__ necessary here??'''
     #   searchSubject = None
      #  searchParams = None


    def mainUI(self) -> None:

        '''Display the main Menu and choose the search type'''

        print("Welcome to SemanticScholar! \n\n")
        mainMsg = "Please choose one of the options below: "
        mainOptions = ["Search for paper", "Search for author", "Keyword search"]

        fwdValue = self.chooseOption(msg=mainMsg, options=mainOptions)

        if fwdValue == "Search for paper":
            self.searchSubject = "paper"
            self.paperUI()
        
        elif fwdValue == "Search for author":
            self.searchSubject = "author"
            self.authorUI

        elif fwdValue == "Keyword search":
            self.searchSubject = "keyword"
            self.keywordUI


    def paperUI(self) -> None:
        
        '''Ask user to enter search parameters for distinctive paper search'''

        paperList = list[str]
        morePapers = True

        while morePapers:

            pMsg = "How would you like to search for the paper?"
            pOptions = ["S2PaperId", "CorpusId", "DOI", "ArXivId", "MAG", "ACL", "PMID", "PMCID", "URL", "Search by title"]

            param = self.chooseOption(msg=pMsg, options=pOptions)

            if param in pOptions and not (param == "Search by title"):
                paramValue = self.enterText(msg="Please enter the chosen ID in the right format: ")
                paperList.append(paramValue)
                self.searchParams["paper_ids"] = paperList

            elif param == "Search by title":
                paramValue = self.enterText(msg="Please enter the title of the paper: ")
                paperList.append(paramValue)
                self.searchParams["query"] = paperList

            #asking for specific fields not implemented: Import question!!

            if self.chooseOption(msg="Would you like to search for another paper?", options=["YES", "NO"]) == "NO":
                morePapers = False
        

    def authorUI(self) -> None:

        '''Ask user to enter search parameters for distinctive author search'''

        authorList = list[str]
        moreAuthors = True

        while moreAuthors:

            aMsg = "How would you like to search for the author?"
            aOptions = ["S2AuthorId", "Search by name"]

            param = self.chooseOption(msg=aMsg, options=aOptions)

            if param == "S2AuthorId":
                paramValue = self.enterText(msg="Please enter the author ID in the right format: ")
                authorList.append(paramValue)
                self.searchParams["author_ids"] = authorList

            elif param == "Search by name":
                paramValue = self.enterText(msg="Please enter the name of the author: ")
                authorList.append(paramValue)
                self.searchParams["query"] = authorList
            
            fwd = self.chooseOption(msg="Would you like to search for another author?", options=["YES", "NO"])
            
            if fwd == "NO":
                moreAuthors = False
                if authorList.len() 


            #asking for specific fields not implemented: Import question!!

    def keywordUI(self) -> None:

        '''Ask user to enter Searchstring and limitations for Keyword search'''
        
        query = self.enterText(msg="Please enter the Query for your Keyword search: ")
        self.searchParams["query"] = query

        year = self.enterText(msg="Please enter the yearspan for your Keyword search. You can press Enter if you don't wish to specify a yearspan: ")
        self.searchParams["year"] = year

        publication_types = self.enterText(msg="Please enter the publication types you'd like to include in your Keyword search. Separate multiple types by comma."+ 
                                           "You can press Enter if you don't wish to specify publication types: ")
        self.searchParams["publication_types"] = publication_types.split(",")

        venue = self.enterText(msg="Please enter the venues for your Keyword search. Separate multiple venues by comma. You can press Enter if you don't wish to specify any venues: ")
        self.searchParams["venue"] = venue.split(",")

        fields_of_study = self.enterText(msg="Please enter the fields of study for your Keyword search. Separate multiple study fields by comma."+ 
                                            "You can press Enter if you don't wish to specify any study fields: ")
        self.searchParams["fields_of_study"] = fields_of_study.split(",")

        open_access = self.chooseOption(msg="Would you like to solely include open Access PDF files to your search results?", options=["YES", "NO"])
        if open_access == "YES":
            self.searchParams["open_access_pdf"] = True
        else:
            self.searchParams["open_access_pdf"] = False

        limit = self.enterText(msg="How many search results should the query include? Please enter a number between 1 and 1000: ")
        self.searchParams["limit"] = limit.format(int)

        #asking for specific fields not implemented: Import question!!


    def chooseOption(self,
                     *,
                     msg: str,
                     options
                     ) -> str:
        question = [inquirer.List(name="Choice",
                                  message=msg,
                                  choices=["%s" % i for i in options],
                                  carousel=False,
                                  ),
                    ]
        choice = inquirer.prompt(questions=question)

        return choice.values
    
    def enterText(self,
                  *,
                  msg: str,
                  ) -> str:
        question = [inquirer.Text(name="Entry", message=msg,)]
        choice = inquirer.prompt(questions=question)

        return choice.values
    

#if __name__ == "mainUI":
 #   test = Semanticscholar_ui()
  #  test.mainUI()



