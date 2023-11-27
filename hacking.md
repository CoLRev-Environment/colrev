#Aufgaben
##Robert
Code verstehen zu ieee.py
Welche Funktionen machen was und können wir diese auch für unseren Issue gebrauchen?
Generell - wenn was nicht bekannt ist, dann raussuchen und aufschreiben

##Amadu
API Key Semantic Scholar - Authentifizierung von Semantic Scholar
Wie kann man den Key verwenden/generiert? (Header) 
Wie wird dieser gespeichert?
--> im Python CLient oder IEEE SearchSource finden sich Beispiele.und direkt bei Semantic Scholar
Generell - wenn was nicht bekannt ist, dann raussuchen und aufschreiben

##Louis
Wie sucht man nach Papers in Semantic Scholar
	--> Searching for papers by Keyword (https://www.semanticscholar.org/product/api/tutorial)
Was ist der "endpoint"? (Auch findbar in crossref.py/ieee.py)
Was ist JSON und wie verwendet man das?
Generell - wenn was nicht bekannt ist, dann raussuchen und aufschreiben

##Peter
Code verstehen zu crossref.py
Welche Funktionen machen was und können wir diese auch für unseren Issue gebrauchen?

Generell - wenn was nicht bekannt ist, dann raussuchen und aufschreiben 

#FRAGEN FUER HACKING SESSIONS

In der __init_: Sollen wir die MD-Search auch initialisieren? Oder legt der von uns auskommentierte Code die SearchSource neu in den Settings an, wenn sie noch nicht vorhanden ist?

Soll es eine Standard Abfrage (Query) geben? Bei den anderen Search S. gibt es das, aber wie sinnvoll ist es wirklich? - Wir sagen nicht sinnvoll

Alle Ergebnisse per Suchbegriff oder auch einzelne Paper suchen können (targeting)?

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


