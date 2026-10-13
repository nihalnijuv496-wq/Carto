from utils.clihelpers import askInt, printMapList, loadWorldFromDb
import os
from datetime import datetime

from database.queries import (
    getAllMaps,
    getMapById,
    getSettlementsForMap,
    getTotalPopulation,
    getLargestSettlement,
    countSettlementsByType,
)
from render.draw_map import saveMap

outputDir = "output"


def exportMap():
    print("\n[Export Map]")

    maps = getAllMaps()
    if not maps:
        print("No maps to export yet - generate one first (option 1).")
        return

    printMapList(maps)
    mapId = askInt("Enter map id to export: ", default=maps[0]["id"])

    world = loadWorldFromDb(mapId)
    if world is None:
        print("No map found with that id.")
        return

    os.makedirs(outputDir, exist_ok=True)
    filename = f"{world.name.replace(' ', '_')}_{world.seed}.png"
    filepath = os.path.join(outputDir, filename)

    saveMap(world, filepath)
    print(f"Saved to {filepath}")


def exportMapDetailsTxt():
    print("\n[Export Map Details (TXT)]")

    maps = getAllMaps()
    if not maps:
        print("No maps to export yet - generate one first (option 1).")
        return

    printMapList(maps)
    mapId = askInt("Enter map id to export details for: ", default=maps[0]["id"])

    mapRow = getMapById(mapId)
    if mapRow is None:
        print("No map found with that id.")
        return

    settlementRows = getSettlementsForMap(mapId)
    totalPop = getTotalPopulation(mapId)
    largest = getLargestSettlement(mapId)
    typeCounts = countSettlementsByType(mapId)

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
        f"Total settlements: {len(settlementRows)}",
        f"Total population:  {totalPop}",
        "Settlements by type:",
    ]

    if typeCounts:
        for typeName, count in typeCounts.items():
            lines.append(f"  {typeName}: {count}")
    else:
        lines.append("  none")

    if largest:
        lines.append(
            f"Largest settlement: {largest['name']} "
            f"({largest['type']}, pop={largest['population']})"
        )

    lines.append("")
    lines.append("--- Settlements (largest first) ---")

    sortedRows = sorted(settlementRows, key=lambda row: row["population"], reverse=True)
    for row in sortedRows:
        notes = f"founded for: {row['notes']}" if row["notes"] else ""
        lines.append(
            f"{row['name']:<16} {row['type']:<10} "
            f"({row['x']:>4}, {row['y']:>4})  pop={row['population']:<6} {notes}".rstrip()
        )

    os.makedirs(outputDir, exist_ok=True)
    fileName = f"{mapRow['name'].replace(' ', '_')}_{mapRow['seed']}_details.txt"
    filePath = os.path.join(outputDir, fileName)

    with open(filePath, "w", encoding="utf-8") as outFile:
        outFile.write("\n".join(lines) + "\n")

    print(f"Saved to {filePath}")
