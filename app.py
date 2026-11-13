import io
import os
import random
import threading
from datetime import datetime

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    abort,
    send_file,
    Response,
)
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.utils import secure_filename

from database.db import initDb, DATA_DIR
from database.queries import (
    saveWorld,
    deleteMap,
    getAllMaps,
    getMapById,
    getSettlementsForMap,
    getTotalPopulation,
    getLargestSettlement,
    countSettlementsByType,
)
from models.world_map import WorldMap
from render.draw_map import buildFigure
from utils.clihelpers import loadWorldFromDb

maxSavedMaps = 200
pngDir = os.path.join(DATA_DIR, "png")

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1)
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["300 per hour"],
    storage_uri="memory://",
)
initDb()
os.makedirs(pngDir, exist_ok=True)

renderLock = threading.Lock()


def pngPathFor(mapId, world=None):
    return os.path.join(pngDir, f"{mapId}.png")


def ensurePng(mapId, world=None):
    """Render once, then serve the file from disk on every later request."""
    path = pngPathFor(mapId)
    if os.path.isfile(path):
        return path

    with renderLock:
        if os.path.isfile(path):  # another request finished while waited
            return path
        if world is None:
            world = loadWorldFromDb(mapId)
        fig = buildFigure(world)
        tempPath = path + ".tmp"
        fig.savefig(tempPath, format="png", dpi=130, bbox_inches="tight")
        plt.close(fig)
        os.replace(tempPath, path)  # atomic
    return path


def getMapDetails(mapId):
    settlements = sorted(
        getSettlementsForMap(mapId), key=lambda row: row["population"], reverse=True
    )
    return {
        "totalPop": getTotalPopulation(mapId),
        "largest": getLargestSettlement(mapId),
        "typeCounts": countSettlementsByType(mapId),
        "settlements": settlements,
    }


def buildDetailsText(mapRow, details):
    settlements = details["settlements"]
    lines = [
        "=" * 50,
        "MAP DETAILS",
        "=" * 50,
        f"Name:      {mapRow['name']}",
        f"Map ID:    {mapRow['id']}",
        f"Seed:      {mapRow['seed']}",
        f"Size:      {mapRow['width']} x {mapRow['height']}",
        f"Created:   {mapRow['created_at']}",
        f"Exported:  {datetime.now().isoformat(sep=' ', timespec='seconds')}",
        "",
        "--- Summary ---",
        f"Total settlements: {len(settlements)}",
        f"Total population:  {details['totalPop']}",
        "Settlements by type:",
    ]

    if details["typeCounts"]:
        for typeName, count in details["typeCounts"].items():
            lines.append(f"  {typeName}: {count}")
    else:
        lines.append("  none")

    largest = details["largest"]
    if largest:
        lines.append(
            f"Largest settlement: {largest['name']} "
            f"({largest['type']}, pop={largest['population']})"
        )

    lines.append("")
    lines.append("--- Settlements (largest first) ---")
    for row in settlements:
        notes = f"founded for: {row['notes']}" if row["notes"] else ""
        lines.append(
            f"{row['name']:<16} {row['type']:<10} "
            f"({row['x']:>4}, {row['y']:>4})  pop={row['population']:<6} {notes}".rstrip()
        )
    return "\n".join(lines) + "\n"


def baseFileName(mapRow):
    return (
        secure_filename(f"{mapRow['name']}_{mapRow['seed']}") or f"map_{mapRow['id']}"
    )


def readInt(fieldName, default, low, high):
    try:
        value = int(request.form.get(fieldName, default))
    except (TypeError, ValueError):
        abort(400)
    return min(max(value, low), high)


def pruneOldMaps():
    maps = getAllMaps()
    while len(maps) >= maxSavedMaps:
        oldestId = min(row["id"] for row in maps)
        deleteMap(oldestId)
        try:
            os.remove(pngPathFor(oldestId))
        except FileNotFoundError:
            pass
        maps = [row for row in maps if row["id"] != oldestId]


@app.route("/")
def index():
    return render_template("index.html", maps=getAllMaps())


@app.route("/generate", methods=["POST"])
@limiter.limit("4 per minute;30 per hour")
def generate():
    name = request.form.get("name", "").strip()[:40] or "Untitled"
    width = readInt("width", 600, 200, 600)
    height = readInt("height", 600, 200, 600)
    count = readInt("count", 6, 1, 30)
    seed = random.randint(0, 999_999)

    pruneOldMaps()
    world = WorldMap(name, width, height, seed)
    world.generate()
    world.placeSettlements(count=count)
    mapId = saveWorld(world)
    ensurePng(mapId, world)
    return redirect(url_for("viewMap", mapId=mapId))


@app.route("/map/<int:mapId>")
def viewMap(mapId):
    mapRow = getMapById(mapId)
    if mapRow is None:
        abort(404)
    return render_template("map.html", mapRow=mapRow, details=getMapDetails(mapId))


@app.route("/map/<int:mapId>/image.png")
def mapImage(mapId):
    mapRow = getMapById(mapId)
    if mapRow is None:
        abort(404)
    return send_file(
        ensurePng(mapId),
        mimetype="image/png",
        as_attachment=bool(request.args.get("download")),
        download_name=f"{baseFileName(mapRow)}.png",
        max_age=3600,
    )


@app.route("/map/<int:mapId>/details.txt")
def mapDetailsText(mapId):
    mapRow = getMapById(mapId)
    if mapRow is None:
        abort(404)
    text = buildDetailsText(mapRow, getMapDetails(mapId))
    return Response(
        text,
        mimetype="text/plain; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{baseFileName(mapRow)}_details.txt"'
        },
    )


@app.route("/healthz")
@limiter.exempt
def healthCheck():
    return "ok"


@app.errorhandler(400)
@app.errorhandler(404)
@app.errorhandler(429)
@app.errorhandler(500)
def showError(error):
    messages = {
        400: "That request wasn’t valid. Check the form values and try again.",
        404: "That map doesn’t exist. It may have been removed to make room for newer ones.",
        429: "Too many maps drawn in a short time. Wait a minute and try again.",
        500: "Something went wrong while drawing. Try again in a moment.",
    }
    code = getattr(error, "code", 500)
    return (
        render_template("error.html", code=code, message=messages.get(code, "")),
        code,
    )


if __name__ == "__main__":
    app.run(debug=False)
