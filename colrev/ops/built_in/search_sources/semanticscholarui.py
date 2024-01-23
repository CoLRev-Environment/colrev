import inquirer
import re
import datetime

class Semanticscholar_ui:

    """Implements the User Interface for the SemanticScholar API Search within colrev"""

    searchSubject = ""
    searchParams = {}

    def main_ui(self) -> None:
        """Display the main Menu and choose the search type"""

        print("\nWelcome to SemanticScholar! \n\n")
        mainMsg = "Please choose one of the options below "
        mainOptions = ["Keyword search", "Search for paper", "Search for author"]

        fwdValue = self.choose_single_option(msg=mainMsg, options=mainOptions)

        if fwdValue == "Search for paper":
            self.searchSubject = "paper"
            self.paper_ui()

        elif fwdValue == "Search for author":
            self.searchSubject = "author"
            self.author_ui()

        elif fwdValue == "Keyword search":
            self.searchSubject = "keyword"
            self.keyword_ui()

        if not self.searchParams:
            print("\n Search cancelled. The program will close.\n")

    def paper_ui(self) -> None:
        """Ask user to enter search parameters for distinctive paper search"""

        paperIDList = []
        queryList = []
        morePapers = True

        while morePapers:

            validationBreak = False

            pMsg = "How would you like to search for the paper?"
            pOptions = [
                "S2PaperId",
                "CorpusId",
                "DOI",
                "ArXivId",
                "MAG",
                "ACL",
                "PMID",
                "PMCID",
                "Search by title",
            ]

            param = self.choose_single_option(msg=pMsg, options=pOptions)

            if param in pOptions and (not param == "Search by title"):
                paramValue = self.enter_text(
                    msg="Please enter the chosen ID in the right format "
                )
                if param == "S2PaperId":
                    while not self.id_validation_with_regex(id=paramValue, regex=r"^[a-zA-Z0-9]+$") and (not validationBreak):
                        paramValue = self.enter_text(
                            msg="Error: Invalid S2PaperId format. Please try again or press Enter."
                        )
                        if not paramValue:
                            validationBreak = True
                
                elif param == "DOI":
                    while not self.id_validation_with_regex(id=paramValue, regex=r"^10\..+$") and (not validationBreak):
                        paramValue = self.enter_text(
                            msg="Error: Invalid DOI format. Please try again or press Enter."
                        )
                        if not paramValue:
                            validationBreak = True
                
                elif param == "ArXivId":
                    while not self.id_validation_with_regex(id=paramValue, regex=r"^\d+\.\d+$") and (not validationBreak):
                        paramValue = self.enter_text(
                            msg="Error: Invalid ArXivId format. Please try again or press Enter."
                        )
                        if not paramValue:
                            validationBreak = True

                elif param == "ACL":
                    while not self.id_validation_with_regex(id=paramValue, regex=r"^\w+-\w+$") and (not validationBreak):
                        paramValue = self.enter_text(
                            msg="Error: Invalid ACL ID format. Please try again or press Enter."
                        )
                        if not paramValue:
                            validationBreak = True

                else:
                    while not self.id_validation_with_regex(id=paramValue, regex=r"^[0-9]+$") and (not validationBreak):
                        paramValue = self.enter_text(
                            msg="Error: Invalid ID format. Please try again or press Enter."
                        )
                        if not paramValue:
                            validationBreak = True

                if not validationBreak:

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
                paramValue = self.enter_text(msg="Please enter the title of the paper ")

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

            if (
                self.choose_single_option(
                    msg="Would you like to search for another paper or enter a different ID?",
                    options=["YES", "NO"],
                )
                == "NO"
            ):
                morePapers = False

    def author_ui(self) -> None:
        """Ask user to enter search parameters for distinctive author search"""

        authorIDList = []
        queryList = []
        moreAuthors = True

        while moreAuthors:

            validationBreak = False

            aMsg = "How would you like to search for the author?"
            aOptions = ["S2AuthorId", "Search by name"]

            param = self.choose_single_option(msg=aMsg, options=aOptions)

            if param == "S2AuthorId":
                paramValue = self.enter_text(
                    msg="Please enter the author ID in the right format "
                )
                while not paramValue.isalnum() and (not validationBreak):
                        paramValue = self.enter_text(
                            msg="Error: Invalid S2AuthorId format. Please try again or press Enter."
                        )
                        if not paramValue:
                            validationBreak = True

                if not validationBreak:

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
                paramValue = self.enter_text(msg="Please enter the name of the author ")
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

            fwd = self.choose_single_option(
                msg="Would you like to search for another author or enter a different ID?",
                options=["YES", "NO"],
            )

            if fwd == "NO":
                moreAuthors = False

    def keyword_ui(self) -> None:
        """Ask user to enter Searchstring and limitations for Keyword search"""

        query = self.enter_text(msg="Please enter the query for your keyword search ")
        while not isinstance(query, str):
            query = self.enter_text(msg="Error: You must enter a query to conduct a search. Please enter a query")
            
        self.searchParams["query"] = query

        year = self.enter_year()
        if year:
            self.searchParams["year"] = year

        publication_types = self.enter_pub_types()
        if publication_types:
            self.searchParams["publication_types"] = publication_types

        venue = self.enter_text(
            msg="Please enter venues. Separate multiple venues by comma. Do not use whitespaces." 
            + " Please press Enter if you don't wish to specify any venues "
        )
        while venue:
            if not self.alnum_and_comma_validation(venue):
                venue = self.enter_text(
                    msg="Error: Invalid format. Please try again or press Enter. Separate multiple inputs by comma."
                )
            else:
                self.searchParams["venue"] = venue.split(",")
                break

        fields_of_study = self.enter_text(
            msg="Please enter fields of study. Separate multiple study fields by comma. Do not use whitespaces."
            + " Please press Enter if you don't wish to specify any study fields "
        )
        while fields_of_study:
            if not self.alnum_and_comma_validation(fields_of_study):
                fields_of_study = self.enter_text(
                    msg="Error: Invalid format. Please try again or press Enter. Separate multiple inputs by comma."
                )
            else:
                self.searchParams["fields_of_study"] = fields_of_study.split(",")
                break

        open_access = self.choose_single_option(
            msg="Would you like to only search for items for which the full text is available as pdf?",
            options=["YES", "NO"],
        )
        if open_access == "YES":
            self.searchParams["open_access_pdf"] = True
        else:
            self.searchParams["open_access_pdf"] = False

    def get_api_key(self, existing_key = None) -> str:
        """Method to get API key from user input"""

        ask_again = True

        if existing_key:
            api_key = existing_key
        else:
            api_key = self.enter_text(
                msg="Please enter a valid API key for SemanticScholar. If you don't have a key, please press Enter."
            )

        while ask_again:
            ask_again = False

            if not api_key:
                print(
                    "WARNING: Searching without an API key might not be successful. \n"
                )
                fwd = self.choose_single_option(
                    msg="Would you like to continue?", options=["YES", "NO"]
                )

                if fwd == "NO":
                    api_key = self.enter_text(msg="Please enter an API key ")
                    ask_again = True
                else:
                    return None

            elif not re.match(r"^\w{40}$", api_key):
                print("Error: Invalid API key.\n")
                fwd = self.choose_single_option(
                    msg="Would you like to enter a different key?", options=["YES", "NO"])

                if fwd == "YES":
                    api_key = self.enter_text(msg="Please enter an API key ")
                    ask_again = True
                else:
                    return None

            else:
                print("\n"+"API key: "+api_key+"\n")
                fwd = self.choose_single_option(
                    msg="Start search with this API key?", options=["YES", "NO"]
                    )

                if fwd == "NO":
                    api_key = self.enter_text(msg="Please enter a different API key ")
                    ask_again = True

        return api_key
    
    def enter_year(self) -> str:
        """Method to ask a specific yearspan in the format allowed by the SemanticScholar API"""

        examples = "Examples for valid yearspans: '2019'; '2012-2020'; '-2022'; '2015-'"
        ask_again = True
        yearspan = self.enter_text(
            msg="Please enter a yearspan. Please press Enter if you don't wish to specify a yearspan"
        )
        while yearspan and ask_again:
            ask_again = False
            if not re.match("|".join([r"^-\d{4}$", r"^\d{4}-?$", r"^\d{4}-\d{4}"]), yearspan):
                print("Error: Invalid yearspan.\n" + examples + "\n")
                yearspan = self.enter_text(
                    msg="Please enter a yearspan."
                        + " Please press Enter if you don't wish to specify a yearspan"
                )
                ask_again = True
            elif re.match(r"^\d{4}-\d{4}", yearspan):
                years = yearspan.split("-")
                a = int(years[0])
                b = int(years[1])
                if (not a < b) or (b > int(datetime.date.today().year)):
                    print("Error: Invalid yearspan.\n" + examples + "\n")
                    yearspan = self.enter_text(
                        msg="Please enter a yearspan."
                            + " Please press Enter if you don't wish to specify a yearspan"
                    )
                    ask_again = True

        return yearspan

    def enter_pub_types(self) -> list:
        """Method to ask a selection of publication types that are allowed by the SemanticScholar API"""

        msg = "Please choose the publication types. If you want to include all publication types, please press Enter"
        options = [
            "Review",
            "JournalArticle",
            "CaseReport",
            "ClinicalTrial",
            "Dataset",
            "Editorial",
            "LettersAndComments",
            "MetaAnalysis",
            "News",
            "Study",
            "Book",
            "BookSection",
        ]
        pub_types = self.choose_multiple_options(msg=msg, options=options)

        return pub_types

    def choose_single_option(
        self,
        *,
        msg: str,
        options,
    ) -> str:
        """Method to display a question with single choice answers to the console using inquirer"""

        question = [
            inquirer.List(
                name="Choice",
                message=msg,
                choices=["%s" % i for i in options],
                carousel=False,
            ),
        ]
        choice = inquirer.prompt(questions=question)

        return choice.get("Choice")

    def choose_multiple_options(
        self,
        *,
        msg: str,
        options,
    ) -> list:
        """Method to display a question with multiple choice answers to the console using inquirer"""

        question = [
            inquirer.Checkbox(
                name="Choice",
                message=msg,
                choices=["%s" % i for i in options],
                carousel=False,
            ),
        ]
        choice = inquirer.prompt(questions=question)

        return choice.get("Choice")

    def enter_text(
        self,
        *,
        msg: str,
    ) -> str:
        """Method to display a question with free text entry answer to the console using inquirer."""

        question = [
            inquirer.Text(
                name="Entry",
                message=msg,
            )
        ]
        choice = inquirer.prompt(questions=question)

        return choice.get("Entry")
    
    def id_validation_with_regex(
            self,
            *,
            id: str,
            regex: re,
    ) -> bool:
        """Method to validate ID formats using a regex as an argument"""

        if re.match(regex, id):
            return True
        
        return False

    def alnum_and_comma_validation(
            self,
            inputString: str,
    ) -> bool:
        """Method to validate an input consisting of words devided by comma. Used for comma separated lists."""

        if re.match(r"^\w+$|^(\w+,\w+)+$", inputString):
            return True
        
        return False
        
#test
    
if __name__ == "__main__":

    test = Semanticscholar_ui()
    test.main_ui()

    if test.searchParams:

        api_test = test.get_api_key()

        print("\nSearch will be conducted with following parameters:\n")
        print("\nSearch Subject: ", test.searchSubject)
        for key, value in test.searchParams.items():
            print("Search parameter: ", key, ":", value)
        print("\nAPI key: ", api_test)

