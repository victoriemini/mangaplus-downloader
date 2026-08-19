import json
import re
import subprocess

from flask import Flask, jsonify


app = Flask(__name__)


@app.get("/health")
def health():
    return jsonify({
        "status": "ok"
    })


@app.post("/run")
def run_downloader():
    try:
        process = subprocess.run(
            ["python", "/app/main.py"],
            capture_output=True,
            text=True,
        )

        output = (
            (process.stdout or "")
            + (process.stderr or "")
        )

        match = re.search(
            r"MANGAPLUS_RESULT=(\{.*\})",
            output,
        )

        if not match:
            return jsonify({
                "success": False,
                "exit_code": process.returncode,
                "error": "MANGAPLUS_RESULT not found",
                "output": output,
            }), 500

        result = json.loads(
            match.group(1)
        )

        return jsonify({
            "success": process.returncode == 0,
            "exit_code": process.returncode,
            "result": result,
        })

    except Exception as error:
        return jsonify({
            "success": False,
            "error": str(error),
        }), 500


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=8787,
    )
