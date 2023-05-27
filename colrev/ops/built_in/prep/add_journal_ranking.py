def __add_journal_ranking_to_metadata(self, record) -> None:
        with open('/Project/test/data/records.bib', encoding="utf-8") as bibtex_file:
            bibtex_str = bibtex_file.read()
            bib_database = bibtexparser.load(bibtex_str)
        journal = record["journal"]
        print(journal)
        return(journal)

def search_in_database(self,journalname, database) -> None:
        pointer = database.cursor()
        pointer.execute('SELECT * FROM main.Ranking WHERE Name = ?', (journalname,))
        content = pointer.fetchall()
        if content is None:
            print("Warte auf andere Anweisung")
        else:
            for row in content:
                print (content)
        database.close() 