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

dash.register_page(__name__, path='/')



def analytics():
        #data=Status.get_analytics()
        #print(data)

        review_manager = colrev.review_manager.ReviewManager(
            # force_mode=force, verbose_mode=verbose, exact_call=EXACT_CALL
        )
        status_operation = review_manager.get_status_operation()

        
        analytic_results = status_operation.get_analytics()

        analytics_df1 = pd.DataFrame(analytic_results)
        analytics_df2 = analytics_df1.transpose()

        analytics_df2['committed_date'] = analytics_df2['committed_date'].apply(timestampToDate)

        scaled_y_lab = max(analytics_df2['search'])

        print(scaled_y_lab) # to be continued with scaling ...

        fig = px.line(analytics_df2, x= 'committed_date', y='search', template="simple_white", title="BurnOut-Chart")
        return fig

# helper functions for analytics
def timestampToDate(timestamp) -> datetime:

    # convert the timestamp to a datetime object in the local timezone
    date = datetime.fromtimestamp(timestamp)

    return date

def scaleSearch(max, search):

    return search



def scaleIncluded(included):
    return included


layout = html.Div([dcc.Graph(figure=analytics())]), html.Div(className="navigation-button", children=[html.A(html.Button("detailed information on synthesized records"), href="http://127.0.0.1:8050/synthesizedrecords")])
        
