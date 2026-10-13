import random
import sys

from database.db import initDb
from database.queries import (
    saveWorld,
    getAllMaps,
    getMapById,
    deleteMap,
    getTotalPopulation,
    getLargestSettlement,
    countSettlementsByType,
)
from models.world_map import WorldMap
from render.draw_map import showMap
from utils.clihelpers import askInt, printMapList, loadWorldFromDb
from utils.export import exportMap, exportMapDetailsTxt


def generateNewMap():
    print("\n[Generate New Map]")

    name = input("Map name (blank for 'Untitled'): ").strip() or "Untitled"

    width = askInt("Width (default 1000): ", default=1000)
    height = askInt("Height (default 1000): ", default=1000)
    settlementCount = askInt("Number of settlements (default 6): ", default=6)

    seed = random.randint(0, 999_999)

    world = WorldMap(name, width, height, seed)
    world.generate()
    world.placeSettlements(count=settlementCount)

    mapId = saveWorld(world)

    print(
        f"\nGenerated and saved '{name}' as map id={mapId} (seed={seed}, {width}x{height})."
    )
    showMap(world=world)
    print(world.summary())


def loadSavedMap():
    print("\n[Load Saved Map]")

    maps = getAllMaps()
    if not maps:
        print("No saved maps yet — generate one first (option 1).")
        return

    printMapList(maps)
    mapId = askInt("Enter map id to load: ", default=maps[0]["id"])

    world = loadWorldFromDb(mapId)
    if world is None:
        print("No map found with that id.")
        return

    print(f"\nLoaded '{world.name}' (seed={world.seed}, {world.width}x{world.height}).")
    showMap(world=world)
    print(world.summary())


def manageMaps():
    while True:
        print("\n===== Manage Maps =====")
        print("1. List all maps")
        print("2. View details for a map (settlements, population)")
        print("3. Delete a map")
        print("4. Back to main menu")

        choice = input("> ").strip()

        if choice == "1":
            manageListMaps()
        elif choice == "2":
            manageViewMapDetails()
        elif choice == "3":
            manageDeleteMap()
        elif choice == "4":
            return
        else:
            print("Invalid choice, please enter a number from 1-4.")


def manageListMaps():
    print("\n[Saved Maps]")
    maps = getAllMaps()
    if not maps:
        print("No saved maps yet — generate one first (option 1).")
        return
    printMapList(maps)


def manageViewMapDetails():
    print("\n[Map Details]")
    maps = getAllMaps()
    if not maps:
        print("No saved maps yet — generate one first (option 1).")
        return

    printMapList(maps)
    mapId = askInt("Enter map id to view: ", default=maps[0]["id"])

    mapRow = getMapById(mapId)
    if mapRow is None:
        print("No map found with that id.")
        return

    totalPop = getTotalPopulation(mapId)
    largest = getLargestSettlement(mapId)
    typeCounts = countSettlementsByType(mapId)

    print(
        f"\n{mapRow['name']}  ({mapRow['width']}x{mapRow['height']}, seed={mapRow['seed']})"
    )
    print(f"  Total population: {totalPop}")
    print(f"  Settlements by type: {typeCounts or 'none'}")
    if largest:
        print(
            f"  Largest settlement: {largest['name']} ({largest['type']}, pop={largest['population']})"
        )


def manageDeleteMap():
    print("\n[Delete Map]")
    maps = getAllMaps()
    if not maps:
        print("No saved maps yet — nothing to delete.")
        return

    printMapList(maps)
    mapId = askInt("Enter map id to delete: ", default=maps[0]["id"])

    mapRow = getMapById(mapId)
    if mapRow is None:
        print("No map found with that id.")
        return

    confirm = (
        input(
            f"Delete '{mapRow['name']}' (id={mapId}) and all its settlements? [y/N]: "
        )
        .strip()
        .lower()
    )
    if confirm == "y":
        deleteMap(mapId)
        print("Deleted.")
    else:
        print("Cancelled.")


menuActions = {
    "1": generateNewMap,
    "2": loadSavedMap,
    "3": manageMaps,
    "4": exportMap,
    "5": exportMapDetailsTxt,
}


def printMenu():
    print("\n===== Carto =====")
    print("1. Generate new map")
    print("2. Load saved map")
    print("3. Manage maps")
    print("4. Export map (PNG)")
    print("5. Export map details (TXT)")
    print("6. Exit")


def main():
    initDb()
    print("Welcome to Carto - a procedural fantasy map generator.")

    while True:
        printMenu()
        choice = input("> ").strip()

        if choice == "6":
            print("Goodbye!")
            sys.exit(0)

        action = menuActions.get(choice)
        if action:
            action()
        else:
            print("Invalid choice, please enter a number from 1-6.")


if __name__ == "__main__":
    main()
