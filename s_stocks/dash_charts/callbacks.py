from dash import Input, Output, State, set_props, no_update, ctx
from data_loader import DataLoader
from chart import Chart
import datetime as dt
from dash.exceptions import PreventUpdate


def register_callbacks(app, data: DataLoader, chart: Chart):
    def update_chart(new_date=False, underlying_change=False, data_change=False):
        fig = chart.plot()
        set_props('graph', {'figure': fig})

    @app.callback(Output('graph', 'figure'),
                  # Output('interval', 'disabled'),
                  Input('interval', 'n_intervals'))
    def update_graph(n):
        auto_update = data.live and data.th.is_open()
        return chart.plot() #, not auto_update

    @app.callback(
        Output('btn_uix', 'children'),
        Input('btn_uix', 'n_clicks'),
        prevent_initial_call=True)
    def toggle_uix(btn_uix):
        data.toggle_uix()
        update_chart(underlying_change=True)
        return data.uix[0]

    @app.callback(
        Output('btn_by_opt', 'children'),
        Input('btn_by_opt', 'n_clicks'),
        prevent_initial_call=True)
    def toggle_by_option(btn_by_opt):
        data.toggle_by_option()
        update_chart(underlying_change=True)
        return data.txt_by_option

    @app.callback(
        Output("mdl_legs", "is_open"),
        # Output("summdata_modal", "is_open"),
        # Output("oc_modal", "is_open"),
        Output("tbl_legs", "data", allow_duplicate=True),
        Input("btn_legs", "n_clicks"),
        # Input("summdata_button", "n_clicks"),
        # Input("oc_button", "n_clicks"),
        prevent_initial_call=True
    )
    def toggle_strike_modal(but_l):  # , but_d, but_o):
        l_modal = d_modal = o_modal = False
        cur_legs = no_update
        match ctx.triggered_id:
            case 'summdata_button':
                d_modal = True
            case 'btn_legs':
                l_modal = True
                cur_legs = data.legs
            case 'oc_button':
                o_modal = True

        return l_modal, cur_legs  # d_modal, o_modal

    @app.callback(
        Output('tbl_legs', 'data', allow_duplicate=True),
        Output('ddn_strategy', 'value', allow_duplicate=True),
        Input('btn_legs_add', 'n_clicks'),
        Input('btn_legs_upd', 'n_clicks'),
        State('tbl_legs', 'data'),
        State('tbl_legs', 'columns'),
        prevent_initial_call=True
    )
    def update_row(btn1, btn2, _data, columns):
        _ = btn1, btn2
        match ctx.triggered_id:
            case "btn_legs_add":
                _data.append({c['id']: 0 for c in columns})
            case "btn_legs_upd":
                _data = data.update_legs(_data)
                update_chart(data_change=True)
        return _data, ""

    @app.callback(
        Output('dt_pick', 'date'),
        Input("btn_prv_wk", "n_clicks"),
        Input("btn_prv_day", "n_clicks"),
        Input("btn_nxt_day", "n_clicks"),
        Input("btn_nxt_wk", "n_clicks"),
        Input('dt_pick', 'date'),
        prevent_initial_call=True)
    def navigate_date(pw, pd, nd, nw, picker_date):
        if ctx.triggered_id == "dt_pick":
            date = dt.datetime.strptime(picker_date, "%Y-%m-%d").date()
            date_delta = None
        else:
            date_delta = {"btn_prv_wk": -5, "btn_prv_day": -1, "btn_nxt_day": 1, "btn_nxt_wk": 5}[ctx.triggered_id]
            date = None
        data.change_date(delta=date_delta, new_date=date)
        update_chart(new_date=True)
        return data.date.isoformat()

    @app.callback(
        Output('inp_time_start', 'value'),
        Output('inp_time_end', 'value'),
        Input('btn_time', 'n_clicks'),
        State('inp_time_start', 'value'),
        State('inp_time_end', 'value'),
        prevent_initial_call=True)
    def update_track_time(btn_set, start, end):
        data.set_track_time(start, end)
        update_chart()
        return data.track_time_start, data.track_time_end

    @app.callback(
        Output('btn_strike', 'children'),
        Input('btn_strike', 'n_clicks'),
        prevent_initial_call=True)
    def update_strike(btn1):
        data.toggle_static_strike()
        update_chart()
        return data.txt_strike

    @app.callback(
        Input('ddn_strategy', 'value'),
        prevent_initial_call=True)
    def update_strategy(strategy_value):
        if len(strategy_value) == 0:
            raise PreventUpdate
        else:
            if data.apply_strategy(strategy_value):
                update_chart()

    @app.callback(
        Output('btn_quote', 'children'),
        Output('btn_quote', 'color'),
        Output('interval', 'disabled', allow_duplicate=True),
        Input('btn_quote', 'n_clicks'),
        prevent_initial_call=True)
    def quote_type(n_clicks):
        data.toggle_quote()
        values = [["H", "warning"], ["L", "success"]][data.live]
        auto_update = data.live and data.th.is_open()
        update_chart()
        return values[0], values[1], not auto_update
