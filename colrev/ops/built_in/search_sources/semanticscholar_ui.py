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

        pMsg = "How would you like to search for the paper?"
        pOptions = ["S2PaperId", "CorpusId", "DOI", "ArXivId", "MAG", "ACL", "PMID", "PMCID", "URL", "Search by title"]

        param = self.chooseOption(msg=pMsg, options=pOptions)

        if param in pOptions and not (param == "Search by title"):
            paramValue = self.enterText(msg="Please enter the chosen ID in the right format: ")
            self.searchParams[param] = paramValue

        elif param == "Search by title":
            paramValue = self.enterText(msg="Please enter the title of the paper: ")
            self.searchParams[param] = paramValue
        

    def authorUI(self) -> None:
        '''Not implemented'''
        print("Success!")

    def keywordUI(self) -> None:
        '''Not implemented'''
        print("Success!")




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
                  options
                  ) -> str:
        question = [inquirer.Text(name="Entry", message=msg,)]
        choice = inquirer.prompt(questions=question)

        return choice.values
    

#if __name__ == "mainUI":
 #   test = Semanticscholar_ui()
  #  test.mainUI()



