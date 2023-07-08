#! /usr/bin/env python3
"""CoLRev dashboard operation: to track project progress through dashboard"""
from __future__ import annotations
from curses import color_pair

import pandas as pd
from dash import Dash, dcc, html, Input, Output, dash_table, State
import bibtexparser
import plotly.express as px

import colrev.review_manager
from datetime import datetime

class Dashboard():

    
    
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
        app = Dash(__name__) 
        data=Dashboard.filteringData()
        
        for title in data:
            if title != "title" and title != "author" and title != "year"and title != "journal":
                data.pop(title)

        app.layout = html.Div(                              # defining th content
            children=[
                html.Div(children=[
                    html.Img(src="assets/favicon.ico", className="logo"), 
                    html.H1(children="-   Dashboard", className= "header-title")], className="header"),

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
                html.Div(id="table_empty", children= []) ,
                        
            
                html.Div([dcc.Graph(figure=Dashboard.visualizationTime(data))], # Including the graphs  
                         style={'width': '49%', 'display': 'inline-block', 'margin': 'auto'}),   
                html.Div([dcc.Graph(figure=Dashboard.visualizationMagazines(data))],
                         style={'width': '49%', 'display': 'inline-block', 'margin': 'auto'}),
                html.Div([dcc.Graph(figure=Dashboard.analytics(data))],
                        style={'margin': 'auto'}) 
            ]) 
        @app.callback(
        Output("table", "data"),
        Output("table_empty", "children"),
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
                    
            return data2, output
            
        return app


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
    

    def analytics(self):
        review_manager = colrev.review_manager.ReviewManager()
        status_operation = review_manager.get_status_operation()
        analytic_results = status_operation.get_analytics()

        analytics_df = pd.DataFrame(analytic_results)
        analytics_df = analytics_df.transpose()

        # print(analytics_df2)

        analytics_df['committed_date'] = analytics_df['committed_date'].apply(timestampToDate)

        max_y_lab = max(analytics_df['atomic_steps'])

        # print(max_y_lab) 

        # scaled_y_lab = max_y_lab / max_y_lab * 100

        analytics_df['scaled_progress'] = analytics_df['completed_atomic_steps'].apply(scaleCompletedAtomicSteps,max = max_y_lab)

        # print(analytics_df2)
        analytics_df2= analytics_df.iloc[::-1]
        # print(analytics_df3)


        fig = px.line(analytics_df2, x= 'committed_date', y='scaled_progress', template="simple_white", title="Burn-Out Chart")
        fig.update_traces(marker_color = '#2596be')
        fig.update_layout(title=dict(text="<b>Burn-Down Chart</b>", font=dict(size=30), automargin=True, x=0.5)
                          #yaxis = dict( tickfont = dict(size=20)),
                          #xaxis = dict( tickfont = dict(size=20))
                          )
        fig.update_xaxes(title_text='Date of Commit', 
                         type='category',
                         title_font= {"size": 20},
                         tickangle = 25,
                         tickfont = dict(size=20)
                         )
        fig.update_yaxes(title_text='Atomic Steps Completed in %',
                         title_font= {"size": 20},
                         tickfont = dict(size=20)
                         )

        return fig
    
    

# helper functions for analytics:
def timestampToDate(timestamp) -> datetime:

    # convert the timestamp to a datetime object in the local timezone
    date = datetime.fromtimestamp(timestamp)
    return date


def scaleCompletedAtomicSteps(steps, max):

    steps = 100 - (steps / max) * 100

    return steps



def main() -> None:

    dashboard = Dashboard()

    try:
        # dashboard.analytics()
        app = dashboard.makeDashboard()
        app.run_server(debug=True)
    except Exception as e: # catching Exception
        print("Fehler:", str(e)) # print error

   