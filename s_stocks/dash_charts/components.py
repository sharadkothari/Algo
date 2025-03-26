import dash_ag_grid as dag
from dash import dcc, Dash, html, Input, Output, callback, dash_table, State, ctx, set_props
import dash_bootstrap_components as dbc


def legs_table(cols, rows):
    return dash_table.DataTable(
        id='legs-table',
        columnDefs=cols,
        rowData=rows,
        editable=True,
        row_deletable=True
    )


def legs_modal(cols, rows):
    return dbc.Modal([
        dbc.ModalHeader(dbc.ModalTitle("Legs Setup")),
        dbc.ModalBody(legs_table(cols, rows)),
        dbc.ModalFooter([
            dbc.Button('Add Row', id='legs_add_rows_button', n_clicks=0),
            dbc.Button('Update', id='legs_update_button', n_clicks=0),
        ])
    ], id="legs_modal", is_open=False)
