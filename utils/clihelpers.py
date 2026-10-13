from database.queries import getMapById, getSettlementsForMap
from models.settlement import makeSettlement, makeSpecialSettlement
from models.world_map import WorldMap


def askInt(prompt, default):
    raw = input(prompt).strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        print(f"Not a number, using default ({default}).")
        return default


def printMapList(maps):
    for row in maps:
        print(
            f"  id={row['id']}  {row['name']}  "
            f"({row['width']}x{row['height']}, seed={row['seed']})  "
            f"created={row['created_at']}"
        )


def loadWorldFromDb(mapId):
    mapRow = getMapById(mapId)
    if mapRow is None:
        return None

    world = WorldMap(mapRow["name"], mapRow["width"], mapRow["height"], mapRow["seed"])
    world.generate()

    for row in getSettlementsForMap(mapId):
        if row["type"] in ("village", "city"):
            settlement = makeSettlement(
                row["name"], row["x"], row["y"], row["population"]
            )
            if row["type"] == "village":
                settlement.foundingReason = row["notes"]
        else:
            settlement = makeSpecialSettlement(
                row["type"], row["name"], row["x"], row["y"]
            )
        world.settlements.append(settlement)

    return world
