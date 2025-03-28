from dash import dcc, Dash, html
import dash_bootstrap_components as dbc
from data_loader import DataLoader
from chart import Chart
from layouthandler import LayoutHandler
from components import Components
from callbacks import register_callbacks


class DashApp:
    def __init__(self, app_name, server, url_base_pathname, debug=False):
        self.app = Dash(name=app_name, server=server, url_base_pathname=url_base_pathname,
                        external_stylesheets=[dbc.themes.BOOTSTRAP])
        if debug:
            self.app.enable_dev_tools(debug=True)  # Enable Dash debug mode

        self.data = DataLoader(app_name)
        self.data.load_data()

        self.chart = Chart(self.data)
        self.com = Components(self.data)

        self.lh = LayoutHandler()

        self.layout()

    def layout(self):
        com = self.com
        self.app.layout = html.Div([
            self.lh.top_panel([
                com.btn_uix,
                com.btn_by_opt,
                com.btn_strike,
                com.btn_legs,
                com.btn_grp_date
            ]),
            self.lh.context_section([dcc.Graph(id='graph', style={'width': '100vw', 'height': '90vh'})]),
            com.legs_modal,
        ])

        register_callbacks(self.app, data=self.data, chart=self.chart)
