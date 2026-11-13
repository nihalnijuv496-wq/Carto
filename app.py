import io
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
from werkzeug.utils import secure_filename

from database.db import initDb
from database.queries import (
    saveWorld,
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

app = Flask(__name__)
initDb()

renderLock = threading.Lock()
pngCache = {}


def renderPng(mapId):
    if mapId in pngCache:
        return pngCache[mapId]

    world = loadWorldFromDb(mapId)
    with renderLock:
        fig = buildFigure(world)
        buffer = io.BytesIO()
        fig.savefig(buffer, format="png", dpi=130, bbox_inches="tight")
        plt.close(fig)

    pngCache[mapId] = buffer.getvalue()
    return pngCache[mapId]


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


@app.route("/")
def index():
    return render_template("index.html", maps=getAllMaps())


@app.route("/generate", methods=["POST"])
def generate():
    name = request.form.get("name", "").strip() or "Untitled"
    width = min(max(int(request.form.get("width", 1000)), 200), 1000)
    height = min(max(int(request.form.get("height", 1000)), 200), 1000)
    count = min(max(int(request.form.get("count", 6)), 1), 30)
    seed = random.randint(0, 999_999)

    world = WorldMap(name, width, height, seed)
    world.generate()
    world.placeSettlements(count=count)
    mapId = saveWorld(world)
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
        io.BytesIO(renderPng(mapId)),
        mimetype="image/png",
        as_attachment=bool(request.args.get("download")),
        download_name=f"{baseFileName(mapRow)}.png",
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


if __name__ == "__main__":
    app.run(debug=True)
