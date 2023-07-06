#! /usr/bin/env python3
"""CoLRev dashboard operation: to track project progress through dashboard"""
from __future__ import annotations
from curses import color_pair

import pandas as pd
from dash import Dash, dcc, html, Input, Output, dash_table, State
import dash
import bibtexparser
import plotly.express as px

import colrev.review_manager
from datetime import datetime

class Dashboard():
    
    def makeDashboard(self):
        app = Dash(__name__, use_pages = True) 
        
        app.layout = html.Div([
        html.H1('Multi-page app with Dash Pages'),

        html.Div(
            [
                html.Div(
                    dcc.Link(
                        f"{page['name']} - {page['path']}", href=page["relative_path"]
                    )
                )
                for page in dash.page_registry.values()
            ]
        ),

        dash.page_container
        ])
        
        return app
    

        

def main() -> None:

    dashboard = Dashboard()

    try:
        app = dashboard.makeDashboard()
        app.run_server(debug=True)
    except Exception as e: # catching Exception
        print("Fehler:", str(e)) # print error

   