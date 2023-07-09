#! /usr/bin/env python3
"""CoLRev dashboard operation: to track project progress through dashboard"""
from __future__ import annotations
from curses import color_pair

import pandas as pd
from dash import Dash, dcc, html, Input, Output, dash_table, State, callback
import dash
import bibtexparser
import plotly.express as px

import colrev.review_manager
from datetime import datetime

dash.register_page(__name__)



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

for title in data:
    if title != "title" and title != "author" and title != "year"and title != "journal":
        data.pop(title)
        
def visualizationTime(data):
    data2 = data.groupby(['year'])['year'].count().reset_index(name='count')
    fig = px.bar(data2, x='year', y='count', template="simple_white", title="Profile of papers published over time", color="year")
    fig.update_traces(marker_color = '#fcb61a')

    fig.update_layout(title=dict(text="<b>Profile of papers published over time</b>", font=dict(size=30), automargin=True, x=0.5)
                        #yaxis = dict( tickfont = dict(size=20)),
                        #xaxis = dict( tickfont = dict(size=20))
                        )
    fig.update_xaxes(title_text='Year', 
                        type='category',
                        title_font= {"size": 20},
                        tickfont = dict(size=20)
                        )
    fig.update_yaxes(title_text='Count',
                        title_font= {"size": 20},
                        tickfont = dict(size=20)
                        )
    return fig

def visualizationMagazines(data):
    data2 = data.groupby(['journal'])['journal'].count().reset_index(name='count')
    fig = px.bar(data2, x='journal', y='count', template="simple_white", title="Papers Published per Journal")
    fig.update_traces(marker_color = '#fcb61a')

    fig.update_layout(title=dict(text="<b>Papers Published per Journal</b>", font=dict(size=30), automargin=True, x=0.5)
                        #yaxis = dict( tickfont = dict(size=20)),
                        #xaxis = dict( tickfont = dict(size=20))
                        )
    fig.update_xaxes(title_text='Journal', 
                        type='category',
                        title_font= {"size": 20},
                        tickfont = dict(size=20)
                        )
    fig.update_yaxes(title_text='Count',
                        title_font= {"size": 20},
                        tickfont = dict(size=20)
                        )

    return fig


layout = html.Div(                              # defining th content
    children=[
        html.Div(className = "options", children=[
            dcc.Dropdown(
                id="sortby",
                options=["index","year", "author (alphabetically)"], 
                placeholder="Sort by..."
            ),
            dcc.Input(type="text", id="search", value="", placeholder="  Search for..."),
        ]),
        html.Div([
            html.Label("Currently Synthesized Records", style={'fontSize': 40, 'font-weight': 'bold'}),  
            dash_table.DataTable(data = data.to_dict('records'),id = "table",
            style_cell = {'font-family': 'Lato, sans-serif',
                            'font-size': '20px',
                            'text-align': 'left'},
            style_header = {'font-weight': 'bold', 
                            'backgroundColor': '#a4ce4a'})
        ]),
        ## Div für Ausgabe wenn keine Ergebnisse bei suche
        html.Div(id="table_empty", children= []) ,
                
    
        html.Div([dcc.Graph(figure=visualizationTime(data), id='time')], # Including the graphs  
            style={'width': '49%', 'display': 'inline-block', 'margin': 'auto'}),   
        html.Div([dcc.Graph(figure=visualizationMagazines(data), id='magazines')],
            style={'width': '49%', 'display': 'inline-block', 'margin': 'auto'}),
        
        html.Div(className="navigation-button",children=
            [html.A(html.Button("back to Burn-Down Chart"), href="http://127.0.0.1:8050/")
        ])
    ])
    
@callback(
    Output("table", "data"),
    Output("table_empty", "children"),
    Output("time", "figure"),
    Output("magazines", "figure"),
    Input("search", "value"),
    )
def update_table(value):
    
    
    data2 = data.copy(deep = True).to_dict('records')

    output = ""

    for row in data.to_dict('records'):
        found = False
        for key in row:
            if value.lower().strip() in str(row[key]).lower():
                found = True
        
        if found is False:  
            data2.remove(row)
        
        if not data2:
            output = "no records found for your search"

       
            
    return data2, output, visualizationTime(pd.DataFrame.from_dict(data2)), visualizationMagazines(pd.DataFrame.from_dict(data2))
