
#Aufgaben
##Robert
validate input from user
update publication types: no string input, but multiple choice list from API
##Amadu
2 und 4
##Louis
1
##Peter
3

#FRAGEN FUER HACKING SESSIONS
GENERELL: Was muss bis zum 20.12. alles stehen? 
	Was darf noch nach dem pull Date verändert werden?
	Wie wird die Präsi aufgebaut sein? PPP oder frei mit Shell?

crossref.py Zeile 77: __crossref_md_filename = Path("data/search/md_crossref.bib")
	Was genau ist diese Datei, wo findet man sie?
	Kann man mehrere Suchen (unterschiedliche Suchparameter in dieser Datei speichern oder werden hier die 
		Feeds gespeichert? Oder was ganz anderes?
	Settings Search Source wie funktioniert das speichern einer result file

api key format validierung: Welches Format hat ein API key bei Semantic Scholar? Wir würden das gerne validieren
#NEXT STEPS
1) Wie speichert man die Search Source "Semantic Scholar" im colrev Projekt - damit die wiederholt abgerufen werdne kann.
	Welche Parameter braucht diese Funktion?
2) Wie und wo speichern wie die Ergebnisse korrekt (results)?
	Wie funktioniert: Update existing record?
3) Wie aktualliseren wir den feed korrekt?
	wie rerun?
4) Wie baut man den header der URL für semantic scholar (damit der api key genutzt werden kann)


#PUSH-ANLEITUNG
--> diese zeile wurde geändert ... pushtest 
	#speichern
	#git add ...dateiname
	#git commit -m "was geändert wurde hier eingeben"
	#git push




