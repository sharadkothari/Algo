import dash_ag_grid as dag
from dash import dcc, Dash, html, Input, Output, callback, dash_table, State, ctx, set_props
import dash_bootstrap_components as dbc
from data_loader import DataLoader
import datetime as dt


class Components:
    def __init__(self, data_loader):
        self.data: DataLoader = data_loader
        ...

    @property
    def btn_quote(self):
        values = [["H", "warning"], ["L", "success"]][self.data.live]
        return dbc.Button(id="btn_quote", children=values[0],  color=values[1])

    @property
    def btn_uix(self):
        return dbc.Button(self.data.uix[0], id="btn_uix", n_clicks=0, outline=True, color="light")

    @property
    def btn_by_opt(self):
        return dbc.Button(self.data.txt_by_option, id="btn_by_opt", n_clicks=0, outline=True, color="light")

    @property
    def btn_strike(self):
        return dbc.Button(self.data.txt_strike, id="btn_strike", n_clicks=0, outline=True, color="light")

    @property
    def tt_btn_strike(self):
        return dbc.Tooltip("Dynamic: η (eta) / Static: μ (mu)", target="btn_strike",  placement="bottom")

    @property
    def btn_legs(self):
        return dbc.Button("Ψ..", id="btn_legs", n_clicks=0, outline=True, color="light")

    @property
    def legs_table(self):
        return dash_table.DataTable(
            id='tbl_legs',
            columns=self.data.columns,
            data=self.data.legs,
            editable=True,
            row_deletable=True
        )

    @property
    def legs_modal(self):
        return dbc.Modal([
            dbc.ModalHeader(dbc.ModalTitle("Legs Setup")),
            dbc.ModalBody(self.legs_table),
            dbc.ModalFooter([
                dbc.Button('Add Row', id='btn_legs_add', n_clicks=0),
                dbc.Button('Update', id='btn_legs_upd', n_clicks=0),
            ])
        ], id="mdl_legs", is_open=False)

    @property
    def btn_grp_date(self):
        return html.Div(
            [html.Button("<<", 'btn_prv_wk'), html.Button("<", 'btn_prv_day'),
             self.date_picker(_id='dt_pick'),
             html.Button(">", 'btn_nxt_day'), html.Button(">>", 'btn_nxt_wk')]
        )

    def date_picker(self, _id):
        holidays = self.data.expiry.holidays
        return dcc.DatePickerSingle(
            date=self.data.date,
            display_format='D-MMM-YY',
            first_day_of_week=1,
            min_date_allowed=dt.date(2023, 9, 1).isoformat(),
            id=_id,
            disabled_days=self.data.expiry.holidays,
        )

    @property
    def btn_grp_time(self):
        return dbc.ButtonGroup([
            dbc.Input(type="time", value=self.data.track_time_start, id="inp_time_start"),
            dbc.Button("set️", 'btn_time', color="secondary"),
            dbc.Input(type="time", value=self.data.track_time_end, id="inp_time_end"),
        ])

    @property
    def intervals(self):
        return dcc.Interval(
            id='interval',
            interval= 1 * 1000 * (1 if self.data.spread.live else 1000),  # in milliseconds
            n_intervals=0, disabled=False)

    @property
    def ddn_strategy(self):
        return dcc.Dropdown(
            list(self.data.strategies),  '', placeholder="select strategy...", id='ddn_strategy',style={"width": "150px"})

    @property
    def div_space(self):
        return html.Div(style={"width": "30px"})
