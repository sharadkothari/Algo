from dash import html


class LayoutHandler:
    def __init__(self):
        ...

    def top_panel(self, children: list):
        return html.Div(children=children, style=self.top_panel_style())

    @staticmethod
    def top_panel_style():
        return {
            "position": "fixed",
            "top": "0",
            "left": "0",
            "width": "100%",
            "height": "50px",
            "background-color": "#333",
            "display": "flex",
            "align-items": "center",
            "padding": "0 15px",
            "box-shadow": "0px 4px 6px rgba(0, 0, 0, 0.1)",
            "z-index": "1000",
        }

    @staticmethod
    def context_section(children):
        return html.Div(children=children, style={"padding-top": "60px", "width": "100vw" })
