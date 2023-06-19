#! /usr/bin/env python3
"""CoLRev dashboard operation: to track project progress through dashboard"""
from __future__ import annotations


import pandas as pd
from dash import Dash, dcc, html
import bibtexparser


class Dashboard():

    def makeTable(self):
        with open(
            "./data/records.bib"
        ) as bibtex_file:  # changing file format to csv for pandas
            bib_database = bibtexparser.load(bibtex_file)
            if not bib_database.entries:  # checking if bib_database file is empty
                raise Exception("Die Datei 'records.bib' ist leer.") # throwing Exception 
        df = pd.DataFrame(bib_database.entries)
        df.to_csv("./data/records.csv", index = True)

        data = (                                            # the data we want to use later
            pd.read_csv("./data/records.csv")
            .query("colrev_status == 'rev_synthesized'")
        )
        data.rename(columns={'Unnamed: 0':'index'}, inplace=True)

        for title in data:
            if title != "title" and title != "author" and title != "year":
                data.pop(title)

        app = Dash(__name__)                                # initializing the dashboard app

        app.layout = html.Div(                              # defining th content
            children=[
                html.Div(
                children=[
                    html.Img(src="assets/favicon.ico", className="logo"), 
                    html.H1(children="DASHBOARD", className= "header-title")], className="header"),

                html.Div(children=[    
                    html.H1(children="CURRENTLY SYNTHESIZED RECORDS", className="table-header"),

                    html.Div(children=[
                        html.Div(children="sort by ", className="menu-title"),
                        dcc.Dropdown(
                            id="sortby",
                            options=["index","year", "author (alphabetically)"],
                        )])
                        ], className="flexboxtable"),
                html.Div(children=[
                    html.Div(children="search: ", className="search for: "),
                    dcc.Input(
                        type="text",
                    ),   
                    html.Button(id="submit-button", children="search")
                ]),                      
                        html.Table(
                            [html.Tr([html.Th(col) for col in data.columns])] + 
                            [html.Tr([html.Td(data.iloc[i][col]) for col in data.columns]) for i in range(len(data))],
                            className="styled-table"),  
                        
            ])


        return app





def main() -> None:

    dashboard = Dashboard()

    try:
        app = dashboard.makeTable()
        app.run_server(debug=True)
    except Exception as e: # catching Exception
        print("Fehler:", str(e)) # print error

   