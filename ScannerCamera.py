from flask import Flask, render_template, request, jsonify
import logging

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/process_scan", methods=["POST"])
def process_scan():
    """
    Receives parsed JSON from the scanned QR code.
    For demo, we just log and return success.
    """
    data = request.get_json(silent=True) or {}
    app.logger.info("Received scanned JSON: %s", data)

    # Do whatever server-side processing you need here (DB, API call, etc.)
    # For demonstration, return the same data + status
    return jsonify({"success": True, "received": data}), 200

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5001)
