#! /usr/bin/env python3
"""CoLRev dashboard operation: to track project progress through dashboard"""
from __future__ import annotations


import pandas as pd
from dash import Dash, dcc, html
import bibtexparser

#TODO: exception werfen/ try catch block, falls records.bib leer ist

with open("./data/records.bib") as bibtex_file:     # changing file format to csv for pandas
    bib_database = bibtexparser.load(bibtex_file)
df = pd.DataFrame(bib_database.entries)
df.to_csv("./data/records.csv", index = True)



data = (                                            # the data we want to use later
    pd.read_csv("./data/records.csv")
    .query("colrev_status == 'rev_synthesized'")
)
data.rename(columns={'Unnamed: 0':'index'}, inplace=True)

data.pop("ID")
data.pop("abstract")
data.pop("fulltext")
data.pop("booktitle")
data.pop("month")
data.pop("publisher")
data.pop("colrev_status")
data.pop("colrev_masterdata_provenance")
data.pop("colrev_origin")
data.pop("colrev_data_provenance")
data.pop("ENTRYTYPE")
data.pop("dblp_key")
data.pop("doi")
data.pop("language")

app = Dash(__name__)                                # initializing the dashboard app

app.layout = html.Div(                              # defining th content
    children=[
        html.Div(children=[html.H1(children="currently synthesized records")]),
        html.Div(children=[
            html.Div(children="sort by ", className="menu-title"),
            dcc.Dropdown(
                id="sortby",
                options=["index","year", "author (alphabetically)"],
            )
        ]),
        html.Table([html.Tr([html.Td(col) for col in data.columns])] + 
        [html.Tr([html.Td(data.iloc[i][col]) for col in data.columns]) for i in range(len(data))])
    ])


def main() -> None:
    print("Here comes the dashboard!!!")
    app.run_server(debug=True)