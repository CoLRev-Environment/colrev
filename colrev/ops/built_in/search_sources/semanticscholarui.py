import inquirer


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

    def paper_ui(self) -> None:
        """Ask user to enter search parameters for distinctive paper search"""

        paperIDList = []
        queryList = []
        morePapers = True

        while morePapers:
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

            if param in pOptions and not (param == "Search by title"):
                paramValue = self.enter_text(
                    msg="Please enter the chosen ID in the right format "
                )

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
                    msg="Would you like to search for another paper?",
                    options=["YES", "NO"],
                )
                == "NO"
            ):
                morePapers = False

        # asking for specific fields not implemented: Import question!!

        print("\nDoing magic...")

    def author_ui(self) -> None:
        """Ask user to enter search parameters for distinctive author search"""

        authorIDList = []
        queryList = []
        moreAuthors = True

        while moreAuthors:
            aMsg = "How would you like to search for the author?"
            aOptions = ["S2AuthorId", "Search by name"]

            param = self.choose_single_option(msg=aMsg, options=aOptions)

            if param == "S2AuthorId":
                paramValue = self.enter_text(
                    msg="Please enter the author ID in the right format "
                )
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
                msg="Would you like to search for another author?",
                options=["YES", "NO"],
            )

            if fwd == "NO":
                moreAuthors = False

        # asking for specific fields not implemented: Import question!!

        print("\nDoing magic...")

    def keyword_ui(self) -> None:
        """Ask user to enter Searchstring and limitations for Keyword search"""

        query = self.enter_text(msg="Please enter the Query for your Keyword search ")
        self.searchParams["query"] = query

        year = self.enter_year(retry=False)
        if year:
            self.searchParams["year"] = year

        publication_types = self.enter_pub_types()
        if publication_types:
            self.searchParams["publication_types"] = publication_types

        venue = self.enter_text(
            msg="Please enter the venues for your Keyword search. Separate multiple venues by comma. You can press Enter if you don't wish to specify any venues "
        )
        if venue:
            self.searchParams["venue"] = venue.split(",")

        fields_of_study = self.enter_text(
            msg="Please enter the fields of study for your Keyword search. Separate multiple study fields by comma."
            + "You can press Enter if you don't wish to specify any study fields "
        )
        if fields_of_study:
            self.searchParams["fields_of_study"] = fields_of_study.split(",")

        open_access = self.choose_single_option(
            msg="If available, would you like to include a direct link to the respective pdf file of each paper to the results?",
            options=["YES", "NO"],
        )
        if open_access == "YES":
            self.searchParams["open_access_pdf"] = True
        else:
            self.searchParams["open_access_pdf"] = False

        limit = self.enter_text(
            msg="How many search results should the query include? Please enter a number between 1 and 1000 "
        )
        self.searchParams["limit"] = limit.format(int)

        # asking for specific fields not implemented: Import question!!

        print("\nDoing magic...")

    def get_api_key(self, *, retry: bool) -> str:
        """Method to get API key from user input"""

        ask_again = True

        if retry:
            print("Your entered API key is not valid.")
            fwd = self.choose_single_option(
                msg="Would you like to enter a different API key?",
                options=["Enter different key", "Continue without key"],
            )

            if fwd == "Continue without key":
                while ask_again:
                    ask_again = False
                    print(
                        "WARNING: Searching without an API key might not be successfull. \n"
                    )
                    fwd = self.choose_single_option(
                        msg="Would you like to continue?", options=["YES", "NO"]
                    )

                    if fwd == "NO":
                        api_key = self.enter_text(msg="Please enter an API key ")
                        if not api_key:
                            ask_again = True
                    else:
                        api_key = None

            else:
                api_key = self.enter_text(msg="Please enter an API key ")

                if not api_key:
                    while ask_again:
                        ask_again = False
                        print(
                            "WARNING: Searching without an API key might not be successfull. \n"
                        )
                        fwd = self.choose_single_option(
                            msg="Would you like to continue?", options=["YES", "NO"]
                        )

                        if fwd == "NO":
                            api_key = self.enter_text(msg="Please enter an API key ")
                            if not api_key:
                                ask_again = True
                        else:
                            api_key = None

        else:
            api_key = self.enter_text(
                msg="Please enter a valid API key for SemanticScholar here. If you don't have a key, please press Enter."
            )

            if not api_key:
                while ask_again:
                    ask_again = False
                    print(
                        "WARNING: Searching without an API key might not be successfull. \n"
                    )
                    fwd = self.choose_single_option(
                        msg="Would you like to continue?", options=["YES", "NO"]
                    )

                    if fwd == "NO":
                        api_key = self.enter_text(msg="Please enter an API key ")
                        if not api_key:
                            ask_again = True
                    else:
                        api_key = None

        return api_key

    def enter_year(
        self,
        *,
        retry: bool,
    ) -> str:
        """Method to ask a specific yearspan in the format allowed by the SemanticScholar API"""

        if retry:
            print("The yearspan you entered seems not to be valid. \n")

        examples = "Here are some examples for valid yearspans: '2019'; '2012-2020'; '-2022'; '2015-'"
        yearspan = self.enter_text(
            msg="Please enter a yearspan for the publications in your results. "
            + examples
            + " You can press Enter if you don't want to specify a yearspan"
        )

        return yearspan

    def enter_pub_types(self) -> list:
        """Method to ask a selection of publication types that are allowed by the SemanticScholar API"""

        msg = "Please choose the publication types you would like to include in your results. If you want to include all publication types, please press Enter"
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
        """Method to display a question with free text entry answer to the console using inquirer"""

        question = [
            inquirer.Text(
                name="Entry",
                message=msg,
            )
        ]
        choice = inquirer.prompt(questions=question)

        return choice.get("Entry")

if __name__ == "__main__":
    # test
    test = Semanticscholar_ui()
    test.main_ui()
    api_test = test.get_api_key(retry=False)
    if api_test == "0":
        api_test = test.get_api_key(retry=True)

    print("\nSearch Subject: ", test.searchSubject)
    for key, value in test.searchParams.items():
        print("Search parameter: ", key, ":", value)
    print("\nAPI key: ", api_test)
