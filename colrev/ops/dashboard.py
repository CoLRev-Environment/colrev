#! /usr/bin/env python3
"""CoLRev dashboard operation: to track project progress through dashboard"""
from __future__ import annotations
from dash import Dash, html
import dash

class Dashboard():
    
    def makeDashboard(self):
        app = Dash(__name__, use_pages = True) 
        
        app.layout = html.Div([
            html.Div([
                    html.Img(src="assets/favicon.ico", className="logo"), 
                    html.H1(children="Dashboard", className= "header-title"),
                    html.H2(children="make progress visible", className= "header-subtitle")], className="header"),


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

   