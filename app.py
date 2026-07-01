from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask import Flask, request, jsonify
from dotenv import load_dotenv
import uuid

from signals import llm_signal, stylometric_signal
from storage import append_entry, get_log, find_entry_by_content_id

load_dotenv()

app = Flask(__name__)
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=[],
    storage_uri="memory://",
)

def compute_confidence(llm_score: float, stylometric_score: float) -> float:
    """Weighted combination: 60% LLM signal, 40% stylometric signal."""
    return round((0.6 * llm_score) + (0.4 * stylometric_score), 3)


def get_attribution(confidence: float) -> str:
    if confidence >= 0.75:
        return "likely_ai"
    elif confidence >= 0.40:
        return "uncertain"
    else:
        return "likely_human"


def get_label(confidence: float) -> str:
    if confidence >= 0.75:
        return (
            "This content shows strong signals of AI generation. Our system is fairly "
            "confident this was AI-written, but no detection method is perfect — if you "
            "believe this is incorrect, you can appeal this classification."
        )
    elif confidence >= 0.40:
        return (
            "We're not confident either way about this content's origin. The signals we "
            "use gave mixed or weak indicators. This label reflects genuine uncertainty, "
            "not a hidden verdict."
        )
    else:
        return (
            "This content shows strong signals of human authorship. Our system found no "
            "significant indicators of AI generation."
        )


@app.route("/submit", methods=["POST"])
@limiter.limit("10 per minute;100 per day")
def submit():
    data = request.get_json()
    text = data.get("text")
    creator_id = data.get("creator_id")

    content_id = str(uuid.uuid4())

    llm_result = llm_signal(text)
    stylo_result = stylometric_signal(text)

    llm_score = llm_result["score"]
    stylo_score = stylo_result["score"]

    confidence = compute_confidence(llm_score, stylo_score)
    attribution = get_attribution(confidence)
    label = get_label(confidence)

    append_entry({
        "content_id": content_id,
        "creator_id": creator_id,
        "attribution": attribution,
        "confidence": confidence,
        "llm_score": llm_score,
        "stylometric_score": stylo_score,
        "status": "classified"
    })

    return jsonify({
        "content_id": content_id,
        "attribution": attribution,
        "confidence": confidence,
        "label": label
    })


@app.route("/appeal", methods=["POST"])
def appeal():
    data = request.get_json()
    content_id = data.get("content_id")
    creator_reasoning = data.get("creator_reasoning")

    original = find_entry_by_content_id(content_id)
    if not original:
        return jsonify({"error": "content_id not found"}), 404

    append_entry({
        "content_id": content_id,
        "status": "under_review",
        "appeal_reasoning": creator_reasoning,
        "original_confidence": original["confidence"],
        "original_attribution": original["attribution"],
        "original_llm_score": original["llm_score"],
        "original_stylometric_score": original["stylometric_score"]
    })

    return jsonify({
        "message": "Appeal received. Your content has been flagged for human review.",
        "content_id": content_id,
        "status": "under_review"
    })


@app.route("/log", methods=["GET"])
def log():
    return jsonify({"entries": get_log()})


if __name__ == "__main__":
    app.run(debug=True, port=5050)