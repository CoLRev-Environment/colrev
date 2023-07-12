#! /usr/bin/env python3
"""CoLRev dashboard operation: to track project progress through dashboard"""
from __future__ import annotations


import pandas as pd
from dash import dcc, html, Input, Output, dash_table, callback
import dash
import bibtexparser
import dash
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dash import callback
from dash import Dash
from dash import dash_table
from dash import dcc
from dash import html
from dash import Input
from dash import Output
from dash import State


dash.register_page(__name__)


with open(
    "./data/records.bib"
) as bibtex_file:  # changing file format to csv for pandas
    bib_database = bibtexparser.load(bibtex_file)
    if not bib_database.entries:  # checking if bib_database file is empty
        raise Exception("Die Datei 'records.bib' ist leer.")  # throwing Exception
df = pd.DataFrame(bib_database.entries)
df.to_csv("./data/records.csv", index=True)
data = pd.read_csv("./data/records.csv").query("colrev_status == 'rev_synthesized'")
data.rename(columns={"Unnamed: 0": "index"}, inplace=True)

for title in data:
    if (
        title != "title"
        and title != "author"
        and title != "year"
        and title != "journal"
    ):
        data.pop(title)


# function from StackOverflow (https://stackoverflow.com/questions/66637861/how-to-not-show-default-dcc-graph-template-in-dash)
def empty_figure():
    figure = go.Figure(go.Scatter(x=[], y=[]))
    figure.update_layout(template=None)
    figure.update_xaxes(showgrid=False, showticklabels=False, zeroline=False)
    figure.update_yaxes(showgrid=False, showticklabels=False, zeroline=False)

    return figure


def visualization_time(data):
    if data.empty:
        return empty_figure()
    data2 = data.groupby(['year'])['year'].count().reset_index(name='count')
    fig = px.bar(data2, x='year', y='count', template="simple_white", title="Profile of papers published over time", color="year")
    fig.update_traces(marker_color = '#fcb61a')

    fig.update_layout(title=dict(text="<b>Profile of papers published over time</b>", font=dict(family='Lato, sans-serif', size=30), automargin=True, x=0.5)
                        #yaxis = dict( tickfont = dict(size=20)),
                        #xaxis = dict( tickfont = dict(size=20))
                        )
    fig.update_xaxes(title_text='Year', 
                        type='category',
                        title_font= dict(family='Lato, sans-serif', size=20),
                        tickfont = dict(family='Lato, sans-serif', size=20)
                        )
    fig.update_yaxes(title_text='Count',
                        title_font= dict(family='Lato, sans-serif', size=20),
                        tickfont = dict(family='Lato, sans-serif', size=20)
                        )
    return fig


def visualization_magazines(data):
    if data.empty:
        return empty_figure()
    data2 = data.groupby(['journal'])['journal'].count().reset_index(name='count')
    fig = px.bar(data2, x='journal', y='count', template="simple_white", title="Papers Published per Journal")
    fig.update_traces(marker_color = '#fcb61a')

    fig.update_layout(title=dict(text="<b>Papers Published per Journal</b>", font=dict(family='Lato, sans-serif', size=30), automargin=True, x=0.5)
                        #yaxis = dict( tickfont = dict(size=20)),
                        #xaxis = dict( tickfont = dict(size=20))
                        )
    fig.update_xaxes(title_text='Journal', 
                        type='category',
                        title_font= dict(family='Lato, sans-serif', size=20),
                        tickfont = dict(family='Lato, sans-serif', size=15)
                        )
    fig.update_yaxes(title_text='Count',
                        title_font= dict(family='Lato, sans-serif', size=20),
                        tickfont = dict(family='Lato, sans-serif', size=15)
                        )

    return fig


layout = html.Div( # defining the content
    children=[
        html.Div(
            children =[
                html.Div(className = "options", 
                    children=[
                        dcc.Dropdown(
                            id="sortby",
                            options=["index","year", "author (alphabetically)"], 
                            placeholder="Sort by..."
                        )]),
                html.Div(className ="options", 
                    children =[
                        dcc.Input(type="text", id="search", value="", placeholder="  Search for..."
                        )])
            ], className="menu"),

        html.Div(
            children=[
                html.Div([
                html.Label("Currently Synthesized Records", style={'font-family': 'Lato, sans-serif','font-weight': 'bold', 'fontSize': 30}),  
                dash_table.DataTable(data = data.to_dict('records'),id = "table",
                style_cell = {'font-family': 'Lato, sans-serif',
                                'font-size': '20px',
                                'text-align': 'left'
                                },
                style_cell_conditional=[{'if': {'column_id': 'year'},'width': '7%', 'text-align': 'center'},
                                         {'if': {'column_id': 'title'},'width': '53%'}],
                style_header = {'font-weight': 'bold', 
                                'backgroundColor': '#006400',
                                'color':'white'},
                style_data = {'whiteSpace': 'normal',
                                'height': 'auto',
                                'border': '1px solid green' },
                style_as_list_view=True,    
                            )
                ]),
                ## Div für Ausgabe wenn keine Ergebnisse bei suche
                html.Div(id="table_empty", children= []) ,
                            
                html.Div([dcc.Graph(figure=visualizationTime(data), id='time')], # Including the graphs  
                    # style={'width': '49%', 'display': 'inline-block', 'margin': 'auto'}
                    ),   
                html.Div([dcc.Graph(figure=visualizationMagazines(data), id='magazines')],
                    # style={'width': '49%', 'display': 'inline-block', 'margin': 'auto'}
                    )
            ], 
        className="wrapper"),
        
        html.Div(className="navigation-button",children=
            [html.A(html.Button("back to Burn-Down Chart"), href="http://127.0.0.1:8050/")
        ])
    ]
)
    
@callback(
    Output("table", "data"),
    Output("table_empty", "children"),
    Output("time", "figure"),
    Output("magazines", "figure"),
    Input("search", "value"),
    Input("sortby", "value"),
)
def update_table(searchvalue, sortvalue):
    sorted_data = data.copy(deep=True)

    output = ""

    if sortvalue == "year":
        sorted_data = sorted_data.sort_values(by=["year"])  # sort by year
    elif sortvalue == "title":
        sorted_data = sorted_data.sort_values(by=["title"])  # sort by title
    elif sortvalue == "author":
        sorted_data = sorted_data.sort_values(by=["author"])  # sort by author

    data2 = sorted_data.copy(deep=True).to_dict("records")

    for row in sorted_data.to_dict("records"):
        found = False
        for key in row:
            if searchvalue.lower().strip() in str(row[key]).lower():
                found = True

        if found is False:
            data2.remove(row)

        if not data2:
            output = "no records found for your search"

    return (
        data2,
        output,
        visualization_time(pd.DataFrame.from_dict(data2)),
        visualization_magazines(pd.DataFrame.from_dict(data2)),
    )
