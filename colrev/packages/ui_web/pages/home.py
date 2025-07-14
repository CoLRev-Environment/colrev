#! /usr/bin/env python3
"""Burn Down Chart is created here"""
from __future__ import annotations

from datetime import datetime

import dash  # pylint: disable=import-error
import pandas as pd
import plotly.express as px  # pylint: disable=import-error
from dash import dcc  # pylint: disable=import-error
from dash import html  # pylint: disable=import-error

import colrev.exceptions as colrev_exceptions
import colrev.review_manager

# dash dependencies optional
# install with pip install colrev[ui_web]
# will fail if not installed

dash.register_page(__name__, path="/")


def analytics() -> px.line:
    """Function creating burn down chart."""

    # get data from get_analytics function
    review_manager = colrev.review_manager.ReviewManager()
    status_operation = review_manager.get_status_operation()
    analytic_results = status_operation.get_analytics()

    analytics_df = pd.DataFrame(analytic_results)
    analytics_df = analytics_df.transpose()

    # change timestamp
    analytics_df["committed_date"] = analytics_df["committed_date"].apply(
        timestamp_to_date
    )

    # y Achse skalieren
    max_y_lab = max(analytics_df["atomic_steps"])

    # check if there are no atomic steps saved
    if max_y_lab == 0:
        raise colrev_exceptions.NoRecordsError

    # completed atomic steps skalieren
    analytics_df["scaled_progress"] = analytics_df["completed_atomic_steps"].apply(
        scale_completed_atomic_steps, max_steps=max_y_lab
    )

    # reverse order of dataframe
    analytics_df2 = analytics_df.iloc[::-1]

    # make and style the chart
    fig = px.line(
        analytics_df2,
        x="committed_date",
        y="scaled_progress",
        template="simple_white",
        title="Burn-Out Chart",
    )
    fig.update_traces(marker_color="#2596be")
    fig.update_layout(
        title={
            "text": "<b>Burn-Down Chart</b>",
            "font": {"size": 30},
            "automargin": True,
            "x": 0.5,
        },
        yaxis_range=[0, 100],
    )
    fig.update_xaxes(
        title_text="Date of Commit",
        type="category",
        title_font={"size": 20},
        tickangle=25,
        tickfont={"size": 20},
    )
    fig.update_yaxes(
        title_text="Atomic Steps Completed in %",
        title_font={"size": 20},
        tickfont={"size": 20},
    )

    return fig


def timestamp_to_date(timestamp: float) -> datetime:
    """Convert the timestamp to a datetime object in the local timezone."""
    date = datetime.fromtimestamp(timestamp)
    return date


def scale_completed_atomic_steps(steps: int, max_steps: int) -> float:
    """Scale completed atomic steps for burn down chart."""
    return 100 - (steps / max_steps) * 100


# html code for the burn down chart
layout = html.Div([dcc.Graph(figure=analytics())], style={"margin": "auto"}), html.Div(
    className="navigation-button",
    children=[
        # button to get to synthesized records
        html.A(
            html.Button("detailed information on synthesized records"),
            href="http://127.0.0.1:8050/synthesizedrecords",
        )
    ],
)
