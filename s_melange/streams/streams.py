from flask import Flask, render_template, json, Response, jsonify
from common.config import data_dir
from common.utils import list_routes, register_service
from pathlib import Path

module_name = Path(__file__).stem

app = Flask(__name__, template_folder=".", static_folder=".")
app.config['TEMPLATES_AUTO_RELOAD'] = True
port = 5002

with open(data_dir / 'M3U8.json', 'r') as f:
    m3u8_links = json.loads(f.read())


@app.route('/0')
def streams():
    return render_template('Stream.html', streams=m3u8_links)


@app.route('/1')
def streams1():
    return render_template('Stream1.html', streams=m3u8_links)


@app.route('/m3u')
def generate_m3u():
    m3u_content = "#EXTM3U\n"

    for channel_name, stream_url in m3u8_links.items():
        m3u_content += f"#EXTINF:-1,{channel_name}\n"
        m3u_content += f"{stream_url}\n"

    return Response(m3u_content, mimetype="audio/x-mpegurl", content_type="application/x-mpegurl")


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

if __name__ == "__main__":
    #app.run(host="0.0.0.0", port=port, debug=True)
    ...