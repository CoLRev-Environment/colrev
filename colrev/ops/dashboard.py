#! /usr/bin/env python3
"""CoLRev dashboard operation: to track project progress through dashboard"""
from __future__ import annotations
from curses import color_pair


import pandas as pd
from dash import Dash, dcc, html
import bibtexparser
import plotly.express as px



class Dashboard():

    app = Dash(__name__) 
    
    def filteringData():
        with open( 
            "./data/records.bib"
        ) as bibtex_file:  # changing file format to csv for pandas
            bib_database = bibtexparser.load(bibtex_file)
            if not bib_database.entries:  # checking if bib_database file is empty
                raise Exception("Die Datei 'records.bib' ist leer.") # throwing Exception 
        df = pd.DataFrame(bib_database.entries)
        df.to_csv("./data/records.csv", index = True)
        data = (pd.read_csv("./data/records.csv").query("colrev_status == 'rev_synthesized'"))
        data.rename(columns={'Unnamed: 0':'index'}, inplace=True)
        return data

    def makeDashboard(self):
        data=Dashboard.filteringData()
        
        for title in data:
            if title != "title" and title != "author" and title != "year"and title != "journal":
                data.pop(title)

        self.app.layout = html.Div(                     #defining the content
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
                html.Div([dcc.Graph(figure=Dashboard.visualizationTime(data))]),    # Including the graph    
                html.Div([dcc.Graph(figure=Dashboard.visualizationMagazines(data))]) 
            ]) 

    def visualizationTime(data):
        data2 = data.groupby(['year'])['year'].count().reset_index(name='count')
        fig = px.bar(data2, x='year', y='count', template="simple_white", title="Profile of papers published over time", color="year")
        return fig
    
    def visualizationMagazines(data):
        data2 = data.groupby(['journal'])['journal'].count().reset_index(name='count')
        fig = px.bar(data2, x='journal', y='count', template="simple_white", title="Profile of papers published over time")
        return fig

    def analytics():
        #data=Status.get_analytics()
        #print(data)

        return

def main() -> None:

    dashboard = Dashboard()

    try:
        dashboard.makeDashboard()
        dashboard.app.run_server(debug=True)
    except Exception as e: # catching Exception
        print("Fehler:", str(e)) # print error

   