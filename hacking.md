#Aufgaben
##Robert

##Amadu

##Louis

##Peter

Wie man nach Papers sucht - Searching for papers by Keyword (https://www.semanticscholar.org/product/api/tutorial)
API Key + Python Client - Authentifizierung von Semantic Scholar
Code verstehen von z.B. ieee.py / crossref.py
Was muss API Klasse beinhalten ieee_api.py -  was braucht man alles, woher kennt man die SearchFields? (muss man das alles auflisten?)

Generell - wenn was nicht bekannt ist, dann raussuchen und aufschreiben 

#FRAGEN FUER HACKING SESSIONS
Alle Ergebnisse per Suchbegriff oder auch einzelne Paper suchen können (targeting)

Was muss alles in die BibTech Datei rein?

Soll unsere Software einen API Key automatisch anfordern können, wenn noch keiner vorhanden ist? Oder soll der Nutzer bei nicht vorhandenem Key selbst einen anfragen und dann manuell in colrev eingeben?
(siehe IEEE Klasse, Zeile 208)
	--> Key jedesmal abfragen, wenn festgestellt wurde, dass es noch keinen gibt z.B. über if(header == none) then ask key
		oder über extra Funktion: addAPIKey(header as String) --> none:

Muss ein externes Package wie das JsonSchema automatisch bei erster Verwendung installiert werden oder können wir das manuell machen? JsonSchema wird in jeder SearchSource verwendet.


Müssen wir bezüglich packages etwas beachten? Muss unser Modul mit der Logik in einem eigenen Package liegen? Falls dazu erstmal nichts weiter beachtet werden muss, würden wir unseren Code einfach in einer SemanticScholar.py-Datei in search_sources ablegen.


#NEXT STEPS
1. SemanticScholar API lesen
2. PythonClient lesen (link in Issuebeschreibung)
3. #search_sources.semanticscholar_api Klasse erstellen (coding-Aufgabe, machen wir zusammen)


#PUSH-ANLEITUNG
--> diese zeile wurde geändert ... pushtest 
#speichern
#für push: git add ...dateiname
#git commit -m "was geändert wurde hier eingeben"
#


