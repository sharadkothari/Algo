from flask import Flask
from shared.utils import greet

app = Flask(__name__)

@app.route("/")
def hello():
    return greet("Microservice 2")

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5001)