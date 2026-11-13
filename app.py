import io
import base64
import random
import threading

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from flask import Flask, render_template, request, redirect, url_for, abort

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
imageCache = {}


def renderMapImage(mapId):
    if mapId in imageCache:
        return imageCache[mapId]

    world = loadWorldFromDb(mapId)
    with renderLock:
        fig = buildFigure(world)
        buffer = io.BytesIO()
        fig.savefig(buffer, format="png", dpi=110, bbox_inches="tight")
        plt.close(fig)

    imageB64 = base64.b64encode(buffer.getvalue()).decode()
    imageCache[mapId] = imageB64
    return imageB64


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
    return render_template(
        "map.html",
        mapRow=mapRow,
        image=renderMapImage(mapId),
        details=getMapDetails(mapId),
    )


if __name__ == "__main__":
    app.run(debug=True)
