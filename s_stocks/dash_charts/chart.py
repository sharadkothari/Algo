import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
from s_stocks.spreads.spread import Spread
import datetime as dt


class Chart:

    def __init__(self, data_loader):
        self.data_loader = data_loader
        self.spread: Spread = self.data_loader.spread

    def left_axis(self):
        axis_list = []
        line_color = {'all': "#0000ff", "pe": "#DC143C", "ce": "#33cc33"}
        sdf = self.spread.compute_spread(by_option=self.data_loader.by_option)
        for key, df in sdf.items():
            if not df.empty:
                opt_types = ['pe', 'ce'] if key == "all" else key
                if key == 'all':
                    axis_list.append(go.Scatter(x=df['date'], y=df['vwap'], mode='lines', line=dict(color="#F5B31E"),
                                                name='vwap', hoverinfo='none'))
                close_values = [leg.df['close'].reset_index(drop=True) for leg in self.spread.legs if
                                leg.opt_type.lower() in opt_types]
                close_df = pd.DataFrame(close_values).T
                all_close_join = close_df.apply(lambda row: " | ".join(row.astype(str)), axis=1).values
                axis_list.append(go.Scatter(
                    x=df['date'], y=df['close'], mode='lines', name=key,
                    line=dict(color=line_color[key]), customdata=all_close_join,
                    hovertemplate='%{y:.1f} <br>%{customdata} <br>'))
        return axis_list

    def right_axis(self):
        axis_list = []
        udf = self.spread.get_underlying_quote(uix=self.data_loader.uix)
        axis_list.append(go.Scatter(x=udf['date'], y=udf['close'].expanding().mean(), mode='lines',
                                    line=dict(color="#A9A9A9", dash='dot'), name='avg', hoverinfo='none'))
        axis_list.append(go.Scatter(x=udf['date'], y=udf['close'], mode='lines', line=dict(color="#A9A9A9"),
                                    name='index', hovertemplate='%{y:.0f}'))
        return axis_list

    @staticmethod
    def add_marker(fig, axis, secondary_y):
        fig.add_scatter(
            x=[pd.to_datetime(axis.x[-1])], y=[axis.y[-1]],
            mode='markers+text',
            text=f"{axis.y[-1]:.1f}",
            textfont=dict(color=axis.line.color or "#0000FF"),
            textposition='middle right',
            marker=dict(color=axis.line.color, size=12),
            secondary_y=secondary_y
        )

    @staticmethod
    def get_colored_time(fig):
        latest_tick_datetime = pd.to_datetime(fig.data[0].x[-1])
        latest_tick_time_str = latest_tick_datetime.time().strftime('%H:%M:%S')
        time_diff_seconds = (dt.datetime.now() - latest_tick_datetime).total_seconds()
        if time_diff_seconds < 30:
            color = 'green'
        elif time_diff_seconds < 60:
            color = 'orange'
        else:
            color = 'red'
        return f'<span style="color:{color}">{latest_tick_time_str}</span>'

    def update_layout(self, fig):
        title = f'{self.data_loader.expiry.underlying()} | {self.data_loader.expiry.dte(self.spread.get_date())}'

        if self.data_loader.live:
            title += f" | {self.get_colored_time(fig)}"

        fig.update_layout(
            title=title,
            showlegend=False,
            xaxis_rangeslider_visible=False,
            margin=dict(l=50, r=0, t=10, b=0),
            title_x=0.03,
            title_y=0.97,
            hovermode='x unified',
            # xaxis=dict(tickformat='%H:%M\n%a %d-%b-%Y')
        )

    def set_annotation(self, fig):
        annotation = [f"{leg.opt_type} | {leg.strike} | {leg.multiplier}x" for leg in self.spread.legs]
        annotation = ' <br>'.join(annotation)
        fig.add_annotation(text=annotation, align='left', xref='paper', yref='paper',
                           x=0.005, y=0.95, bordercolor='black', borderwidth=0, showarrow=False,
                           bgcolor="#E6ECF5", )

    @staticmethod
    def empty_fig():
        return {
            "layout": {
                "xaxis": {"visible": False}, "yaxis": {"visible": False},
                "annotations": [{
                    "text": dt.datetime.now().strftime("%a %d-%b-%y  %H:%M:%S"),
                    "xref": "paper",
                    "yref": "paper",
                    "showarrow": False,
                    "font": {"size": 30, }
                }]
            }}

    def add_vertical_line(self, fig):
        if self.data_loader.static_strike:
            vertical_line_time = pd.Timestamp(f'{self.data_loader.date} {self.data_loader.track_time_start}')
            fig.add_vline(x=vertical_line_time, line=dict(color="red", width=3, dash="dash"))

    def plot(self):

        #if self.data_loader.live and dt.datetime.now().time() < self.data_loader.th.start:
        #    return self.empty_fig()

        fig = make_subplots(specs=[[{"secondary_y": True}]])

        for left_axis in self.left_axis():
            fig.add_trace(left_axis, secondary_y=False)
            self.add_marker(fig, left_axis, secondary_y=False)

        for i, right_axis in enumerate(self.right_axis()):
            fig.add_trace(right_axis, secondary_y=True)
            if i == 1:
                self.add_marker(fig, right_axis, secondary_y=True)

        self.update_layout(fig)
        self.set_annotation(fig)
        self.add_vertical_line(fig)
        return fig


if __name__ == '__main__':
    from data_loader import DataLoader

    d = DataLoader("dash1")
    c = Chart(d)
    _fig = c.plot()
    _fig.show()
