import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
from s_stocks.spreads.spread import Spread
import datetime as dt


class Chart:

    def __init__(self, data_loader):
        self.data_loader = data_loader
        self.spread: Spread = self.data_loader.spread
        self._pivot_cache = None

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

    def right_axis(self, udf):
        axis_list = []
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

    def compute_rolling_pivot(self, udf, window_start="9:16", window_end="10:15"):

        # filter first-window data
        date = self.spread.get_date()
        start_time = pd.to_datetime(f"{date} {window_start}")
        end_time = pd.to_datetime(f"{date} {window_end}")

        last_ts = udf["date"].iloc[-1]
        if last_ts > end_time and self._pivot_cache is not None:
            return self._pivot_cache

        df = udf[(udf["date"] >= start_time) & (udf["date"] <= end_time)]

        if df.empty:
            return None  # no pivot

        h = df["high"].max()
        l = df["low"].min()
        c = df["close"].iloc[-1]

        pp = (h + l + c) / 3
        r1 = 2 * pp - l
        s1 = 2 * pp - h
        r2 = pp + (h - l)
        s2 = pp - (h - l)

        pivot =  {
            "PP": pp, "R1": r1, "S1": s1, "R2": r2, "S2": s2,
            "H": h, "L": l, "C": c,
        }

        if last_ts >= end_time:
            self._pivot_cache = pivot

        return pivot

    def pivot_lines(self, udf):

        pivot = self.compute_rolling_pivot(udf)
        traces = []

        if pivot is None:
            return []

        colors = {
            "PP": "#8B008B",  # dark magenta
            "R1": "#FF4500",
            "S1": "#1E90FF",
            "R2": "#B22222",
            "S2": "#4169E1",
        }

        for key, val in pivot.items():
            if key in ["PP", "R1", "S1", "R2", "S2"]:
                traces.append(go.Scatter(
                    x=[udf['date'].iloc[0], udf['date'].iloc[-1]],
                    y=[val, val],
                    mode='lines',
                    line=dict(color=colors[key], width=1.2, dash="dash"),
                    name=f"pivot_{key}",
                    hovertemplate=f"{key}: {val:.1f}<extra></extra>"
                ))

        return traces


    def plot(self):

        if self.data_loader.live and dt.datetime.now().time() < self.data_loader.th.start:
            return self.empty_fig()

        fig = make_subplots(specs=[[{"secondary_y": True}]])

        for left_axis in self.left_axis():
            fig.add_trace(left_axis, secondary_y=False)
            self.add_marker(fig, left_axis, secondary_y=False)

        udf = self.spread.get_underlying_quote(uix=self.data_loader.uix)
        for i, right_axis in enumerate(self.right_axis(udf = udf)):
            fig.add_trace(right_axis, secondary_y=True)
            if i == 1:
                self.add_marker(fig, right_axis, secondary_y=True)

        #for pivot_line in self.pivot_lines(udf=udf):
        #    fig.add_trace(pivot_line, secondary_y=True)

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
