from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
from utils import analyze_text, extract_text_from_file
import os

app = Flask(
    __name__,
    static_folder=os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'static')),
    template_folder=os.path.abspath(os.path.join(os.path.dirname(__file__), 'templates'))
)

CORS(app)  # Frontend bilan o‘zaro ishlash uchun CORS ni yoqamiz

@app.route("/")
def index():
    return render_template("index.html")

def process_text_input(text):
    cleaned_text = text.strip()
    corrected_text, error_words, suggestions_map = analyze_text(cleaned_text)
    return {
        "correctedText": corrected_text,
        "errorWords": error_words,
        "suggestionsMap": suggestions_map
    }

@app.route("/analyze", methods=["POST"])
def analyze():
    try:
        data = request.get_json()
        text = data.get("text", "")
        result = process_text_input(text)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": f"Tahlil qilishda xatolik yuz berdi: {str(e)}"}), 500

@app.route("/upload", methods=["POST"])
def upload_file():
    try:
        file = request.files.get("file")
        if file:
            content = extract_text_from_file(file)
            result = process_text_input(content)
            return jsonify(result)
        return jsonify({"error": "Hech qanday fayl yuborilmadi."}), 400
    except Exception as e:
        return jsonify({"error": f"Faylni o‘qishda xatolik: {str(e)}"}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug)
