from flask import Flask, request, jsonify
from dotenv import load_dotenv
import uuid

load_dotenv()

app = Flask(__name__)


@app.route("/submit", methods=["POST"])
def submit():
    data = request.get_json()
    text = data.get("text")
    creator_id = data.get("creator_id")

    # Stub response — proves the route works before we wire in real logic
    content_id = str(uuid.uuid4())
    return jsonify({
        "content_id": content_id,
        "attribution": "placeholder",
        "confidence": 0.0,
        "label": "placeholder label"
    })


if __name__ == "__main__":
    app.run(debug=True, port=5050)