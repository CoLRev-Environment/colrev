#! /usr/bin/env python3
"""CoLRev dashboard operation: to track project progress through dashboard"""
from __future__ import annotations

from curses import color_pair
from datetime import datetime

import bibtexparser
import dash
import pandas as pd
import plotly.express as px
from dash import Dash
from dash import dash_table
from dash import dcc
from dash import html
from dash import Input
from dash import Output
from dash import State

import colrev.review_manager


class Dashboard:
    # constructs header for the dashboard website
    def makeDashboard(self):
        app = Dash(__name__, use_pages=True)

        app.layout = html.Div(
            [
                html.Div(
                    [
                        html.Img(src="assets/favicon.ico", className="logo"),
                        html.H1(children="-   Dashboard", className="header-title"),
                    ],
                    className="header",
                ),
                dash.page_container,
            ]
        )

        return app


def main() -> None:
    dashboard = Dashboard()

    try:
        app = dashboard.makeDashboard()
        app.run_server(debug=True)
    except Exception as e:  # catching Exception
        print("Fehler:", str(e))  # print error
