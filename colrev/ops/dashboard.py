#! /usr/bin/env python3
"""CoLRev dashboard operation: to track project progress through dashboard"""
from __future__ import annotations


import pandas as pd
from dash import Dash, dcc, html
import bibtexparser
import plotly.express as px



class Dashboard():

    app = Dash(__name__) 
    
    def filteringData ():
        data = (pd.read_csv("./data/records.csv").query("colrev_status == 'rev_synthesized'"))
        data.rename(columns={'Unnamed: 0':'index'}, inplace=True)
        return data

    def makeTable(self) -> None:
        with open( 
            "./data/records.bib"
        ) as bibtex_file:  # changing file format to csv for pandas
            bib_database = bibtexparser.load(bibtex_file)
            if not bib_database.entries:  # checking if bib_database file is empty
                raise Exception("Die Datei 'records.bib' ist leer.") # throwing Exception 
        df = pd.DataFrame(bib_database.entries)
        df.to_csv("./data/records.csv", index = True)

        data= Dashboard.filteringData()
        

        for title in data:
            if title != "title" and title != "author" and title != "year":
                data.pop(title)

        # app = Dash(__name__)                                # initializing the dashboard app

        self.app.layout = html.Div(                              # defining th content
            children=[
                html.Div(
                children=[
                    html.Img(src="assets/favicon.ico", className="logo"), 
                    html.H1(children="DASHBOARD", className= "header-title")], className="header"),

                html.Div(children=[    
                    html.H1(children="CURRENTLY SYNTHESIZED RECORDS", className="table-header"),

                    html.Div(children=[
                        dcc.Dropdown(
                            id="sortby",
                            options=["index","year", "author (alphabetically)"],
                        )])
                        ], className="flexboxtable"),
                html.Div(children=[
                    html.Div(children="search: ", className="search-box"),
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
        # return self.app


    def visualization(self) -> None:

        with open( 
            "./data/records.bib"
        ) as bibtex_file:  # changing file format to csv for pandas
            bib_database = bibtexparser.load(bibtex_file)
            if not bib_database.entries:  # checking if bib_database file is empty
                raise Exception("Die Datei 'records.bib' ist leer.") # throwing Exception 
        df = pd.DataFrame(bib_database.entries)
        df.to_csv("./data/records.csv", index = True)

        data= Dashboard.filteringData()
        helperData = data

        helperData.drop(["author"], axis=1)
        # helperData.groupby('year')

        data2 = pd.DataFrame({'year': [helperData.groupby("year")],
                            'papers published': [helperData.groupby("year")["title"].count()]})
        
        self.app.layout = html.Div(
        
            children=[dcc.Graph(

                id="papers-published-over-time",

                config={"displayModeBar": False},

                figure={

                    "data2": [

                        {

                            "x": data2["year"],

                            "y": data2["papers published"],

                            "type": "bar",

                            "hovertemplate": (

                                "$%{y:.2f}<extra></extra>"

                            ),
                        
                        }
                    ]
                  
                }
            )]
        )



        # fig1 = px.bar(data2, x='year', y='papers published')
        #print("hi")
        #fig1.show()'








def main() -> None:

    dashboard = Dashboard()

    try:
        #dashboard.makeTable()
        dashboard.visualization()
        # app = dashboard.makeTable()
        dashboard.app.run_server(debug=True)
    except Exception as e: # catching Exception
        print("Fehler:", str(e)) # print error

   