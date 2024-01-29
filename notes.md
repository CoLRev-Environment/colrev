##Frage1: Wie wird SemanticScholar als SearchSource gespeichert, sodass man wieder darauf zugreifen kann?

Methode #add_endpoint
	Fügt Searchsource zu colrev hinzu - mit der Operation (googlen!) und der darin enthaltenen Funktion add_api_source()
	ansonsten cleane Variante: colrev.settings.SearchSource(endpoint, filename, search_type, search_parameters, [comment])
	filename wird mit operation.get_unique_filename() festgelegt: Hier kann ein kompletter Pfad auch mit eingegebenen Query-Parametern übergeben werden

#Fragen/points of interest
