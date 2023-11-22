##IEEE 

#ieee_api.py
	class XPLORE stellt das Objekt dar, das die query bestimmt
	Dem Objekt können verschiedene Parameter übergeben werden
	Methode callAPI ruft in Kombination mit queryAPI die API mit der gebauten query ab und gibt diese im richtigen Format zurück
	Methode formatData formatiert die Daten ins gewünschte Format - siehe .md-Datei sind bestimmte Dateiformate gewünscht und für diese SearchSource praktischer als andere
	Methoden buildQuery und buildOpenAccessQuery bauen die url, die die konkrete Anfrage an die API stellt - das Format und die einzelnen Parameter der url stehen in der .md-Datei
	Daten werden standardmäßig im json-Format als String ausgegeben - optional sind XML-Format und ein Objekt statt eines Strings
	Methoden zu Beginn der Klasse wichtig für Einstellungen, die dann im Interface gemacht werden - kann wahrscheinlich übernommen werden (gleiche Methoden bei crossref?)

#ieee.py
	"Main" für den Aufruf der Query und die Deklaration der Search Source an sich
	zu Beginn: Einstellungen wie short_name, docs_link oder die url der search source werden definiert
	unter SETTINGS wird der api_key festgelegt - sollte kein Key vorliegen, fragt die Methode "__get_api_key" den User nach einem gültigen Key und updated die Eingabe mit dem environment manager
	Key wird beim Ausführen der Query direkt abgefragt
	Methode __run_api_search führt Suche aus und speichert von der Query aus der ieee.api-Klasse gelieferte und formatierte Daten in einer Datei im Ordner "records"
	review manager nimmt Veränderungen an den Eigenschaften der Klasse vor, wird in __init__ initialisiert
	

#Fragen/points of interest
	Colrev-Main irgendwo zu finden? Wäre interessant zu wissen, wie das Hauptprogramm die Search_Sources ansteuert und welche Funktionen wann wo benutzt werden
	Suchfelder und Query-Eigenschaften werden sich bei uns ähneln - aber brauchen wir alle Methoden aus der IEEE-Klasse auch?
	
