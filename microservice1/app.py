from flask import Flask
from shared.utils import greet
from shared.common_models import SharedModel

app = Flask(__name__)

@app.route("/")
def hello():
    shared_model = SharedModel("Shared Data")
    return f"{greet('Microservice 1')} and {shared_model.get_value()}"

@app.route("/test")
def test():
    return "Test"

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5030)