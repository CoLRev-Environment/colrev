import inquirer


class Semanticscholar_ui():

    def chooseOption(self,
                     *,
                     msg: str,
                     options
                     ) -> dict:
        question = [inquirer.List(name="Choice",
                                  message=msg,
                                  choices=["%s" % i for i in options],
                                  carousel=False,
                                  ),
                    ]
        choice = inquirer.prompt(questions=question)
        print(list(choice.values()))
        return choice

def main():
    myList = [
        'author',
        'whatever',
        'something'
    ]

    test = Semanticscholar_ui()
    choice = test.chooseOption(msg="Choose something:", options=myList)
    print(list(choice.values()))

    if 'author' in list(choice.values()) :
        print("Author has been selected")

main()




