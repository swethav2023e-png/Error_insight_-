"""
Web routes for LogHealth dashboard UI.
"""


from flask import Blueprint, render_template

web_bp = Blueprint("web", __name__)


@web_bp.route("/")
def index():
    """Render main dashboard single-page interface."""
    return render_template("index.html")
