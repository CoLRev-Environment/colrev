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
df.to_csv("./data/records.csv", index = False)


data = (                                            # the data we want to use later
    pd.read_csv("./data/records.csv")
    .query("colrev_status == 'rev_synthesized'")
)

app = Dash(__name__)                                # initializing the dashboard app

app.layout = html.Div(                              # defining th content
    children=[
        html.H1(children="Colrev Dashboard"),
    ]
)

def main() -> None:
    print("Here comes the dashboard!!!")
    app.run_server(debug=True)