from flask import Flask, Response, jsonify, render_template
from pathlib import Path
from ticking_handler import TickingHandler
import time
import json
from common.utils import list_routes, register_service

app = Flask(__name__, template_folder=".", static_folder=".")
app.config['TEMPLATES_AUTO_RELOAD'] = True
module_name = Path(__file__).stem
port = 5024
ticking = TickingHandler()


@app.route('/events')
def sse():
    def event_stream():
        while True:
            data = {
                'tick_time': ticking.tick_last_time,
                'candle_time': ticking.candle_last_time,
                'current_time': time.strftime("%H:%M:%S")
            }
            yield f"data: {json.dumps(data)}\n\n"
            time.sleep(5)

    return Response(event_stream(), content_type='text/event-stream')


@app.route('/status')
def status():
    return jsonify({
        'tick_last_time': ticking.tick_last_time,
        'candle_last_time': ticking.candle_last_time,
        'current_time': time.strftime("%H:%M:%S")
    })

@app.route('/')
def serve_dashboard():
    return render_template('ticking.html')

@app.route("/routes", methods=["GET"])
def get_routes():
    return list_routes(app)

@app.route("/register")
def register():
    return register_service(module_name=module_name, port=port)


@app.route("/health", methods=["GET"])
def health_check():
    return jsonify({"status": "ok"}), 200


register()

if __name__ == '__main__':
    app.run(host="0.0.0.0", debug=True, port=port)

