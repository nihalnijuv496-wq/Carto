import numpy as np

biomeColors = {
    "deep_ocean": "#101038",
    "ocean": "#3c3cb4",
    "ice": "#a0a0ff",
    "coast": "#f7e9a0",
    "plains": "#8db360",
    "forest": "#056621",
    "deep_forest": "#004113",
    "desert": "#faeac1",
    "swamp": "#2c422b",
    "mountain": "#737373",
    "mountain_snow": "#e0e0e0",
    "snowy_land": "#ffffff",
}

deepOceanMax = 0.18
oceanMax = 0.30
coastMax = 0.35
mountainMin = 0.75
snowPeakMin = 0.90
coldMax = 0.05
hotMin = 0.70

desertMoistureMax = 0.35
swampMoistureMin = 0.60
swampMaxElevation = 0.50
forestMoistureMin = 0.55
deepForestElevMin = 0.55

speckRadius = 6
speckPasses = 1

iceMinReach = 1
iceReachFraction = 0.02
iceMaxReachFloor = 3
iceShoreLink = 2


def bilinearUpscale(lowRes, outHeight, outWidth):
    lowH, lowW = lowRes.shape

    ys = np.linspace(0, lowH - 1, outHeight)
    xs = np.linspace(0, lowW - 1, outWidth)

    y0 = np.floor(ys).astype(int)
    x0 = np.floor(xs).astype(int)
    y1 = np.clip(y0 + 1, 0, lowH - 1)
    x1 = np.clip(x0 + 1, 0, lowW - 1)

    yf = (ys - y0).reshape(-1, 1)
    xf = (xs - x0).reshape(1, -1)

    topLeft = lowRes[np.ix_(y0, x0)]
    topRight = lowRes[np.ix_(y0, x1)]
    bottomLeft = lowRes[np.ix_(y1, x0)]
    bottomRight = lowRes[np.ix_(y1, x1)]

    top = topLeft * (1 - xf) + topRight * xf
    bottom = bottomLeft * (1 - xf) + bottomRight * xf
    return top * (1 - yf) + bottom * yf


def smooth(grid, passes=2):
    result = grid.copy()
    for _ in range(passes):
        up = np.roll(result, -1, axis=0)
        down = np.roll(result, 1, axis=0)
        left = np.roll(result, -1, axis=1)
        right = np.roll(result, 1, axis=1)
        result = (result + up + down + left + right) / 5.0
    return result


def normalize(grid):
    return (grid - grid.min()) / (grid.max() - grid.min())


def normalizeStretched(grid, lowPct=2, highPct=98):
    lo, hi = np.percentile(grid, [lowPct, highPct])
    return np.clip((grid - lo) / (hi - lo), 0.0, 1.0)


def lowResField(width, height, seed, scale, smoothPasses=2):
    rng = np.random.default_rng(seed)
    lowH = max(2, height // scale + 2)
    lowW = max(2, width // scale + 2)
    raw = bilinearUpscale(rng.random((lowH, lowW)), height, width)
    return smooth(raw, passes=smoothPasses)


def layeredNoise(width, height, seed, bigScale=8, detailScale=3, detailWeight=0.25):
    bigLayer = lowResField(width, height, seed, bigScale, smoothPasses=0)
    detailLayer = lowResField(width, height, seed + 7, detailScale, smoothPasses=0)
    combined = (1 - detailWeight) * bigLayer + detailWeight * detailLayer
    return smooth(combined, passes=2)


def generateElevation(width, height, seed):
    continent = lowResField(
        width, height, seed, scale=max(width, height) // 2, smoothPasses=4
    )
    texture = layeredNoise(
        width, height, seed, bigScale=14, detailScale=6, detailWeight=0.15
    )

    elevation = 0.85 * continent + 0.15 * texture
    elevation = normalize(elevation)

    lakeNoise = lowResField(
        width, height, seed + 500, scale=max(width, height) // 5, smoothPasses=3
    )
    lakeNoise = normalize(lakeNoise)
    isSolidLand = elevation > 0.45
    isLake = isSolidLand & (lakeNoise > 0.94)
    elevation = np.where(isLake, 0.10, elevation)

    elevation = elevation**1.5
    return elevation


def generateTemperature(width, height, seed):
    noise = layeredNoise(
        width, height, seed, bigScale=20, detailScale=5, detailWeight=0.2
    )
    return normalizeStretched(noise)


def generateIceNoise(width, height, seed):
    noise = layeredNoise(
        width,
        height,
        seed + 3000,
        bigScale=max(4, max(width, height) // 20),
        detailScale=max(2, max(width, height) // 60),
        detailWeight=0.4,
    )
    return normalize(noise)


def generateTerrain(width, height, seed):
    elevation = generateElevation(width, height, seed)
    moisture = normalize(
        layeredNoise(width, height, seed + 1000, bigScale=21, detailScale=4)
    )
    temperature = generateTemperature(width, height, seed + 2000)
    iceNoise = generateIceNoise(width, height, seed)

    return elevation, moisture, temperature, iceNoise


def distanceFromMask(mask, maxDist):
    dist = np.full(mask.shape, maxDist + 1, dtype=np.int32)
    dist[mask] = 0
    reached = mask.copy()
    frontier = mask.copy()

    for step in range(1, maxDist + 1):
        p = np.pad(frontier, 1)
        grown = (
            p[:-2, 1:-1]
            | p[2:, 1:-1]
            | p[1:-1, :-2]
            | p[1:-1, 2:]
            | p[:-2, :-2]
            | p[:-2, 2:]
            | p[2:, :-2]
            | p[2:, 2:]
        )
        new = grown & ~reached
        if not new.any():
            break
        dist[new] = step
        reached |= new
        frontier = new

    return dist


def windowCount(mask, radius):
    p = np.pad(mask.astype(np.int32), radius)
    c = p.cumsum(axis=0).cumsum(axis=1)
    c = np.pad(c, ((1, 0), (1, 0)))
    h, w = mask.shape
    k = 2 * radius + 1
    return c[k : k + h, k : k + w] - c[0:h, k : k + w] - c[k : k + h, 0:w] + c[0:h, 0:w]


def removeSpecks(biomes, radius=None, passes=None):
    radius = speckRadius if radius is None else radius
    passes = speckPasses if passes is None else passes
    land = [
        "plains",
        "forest",
        "deep_forest",
        "desert",
        "swamp",
        "mountain",
        "mountain_snow",
        "snowy_land",
    ]
    for _ in range(passes):
        isLand = np.isin(biomes, land)
        counts = np.stack([windowCount(biomes == name, radius) for name in land])
        winner = np.array(land, dtype=object)[counts.argmax(axis=0)]
        own = np.stack([biomes == name for name in land]).argmax(axis=0)
        ownCount = np.take_along_axis(counts, own[None], axis=0)[0]
        change = isLand & (counts.max(axis=0) > ownCount)
        biomes = np.where(change, winner, biomes)
    return biomes


def applyIce(biomes, elevation, iceNoise):
    height, width = elevation.shape

    isSnow = (biomes == "snowy_land") | (biomes == "mountain_snow")
    if not isSnow.any():
        return biomes

    maxReach = max(iceMaxReachFloor, int(max(width, height) * iceReachFraction))

    maxShore = maxReach * iceShoreLink
    distToSnow = distanceFromMask(isSnow, maxShore)
    shoreReach = iceMinReach + iceNoise * (maxShore - iceMinReach)
    snowyShore = (biomes == "coast") & (distToSnow <= shoreReach)
    biomes[snowyShore] = "snowy_land"
    isSnow = isSnow | snowyShore

    dist = distanceFromMask(isSnow, maxReach)
    reach = iceMinReach + iceNoise * (maxReach - iceMinReach)
    isWater = elevation < oceanMax
    biomes[isWater & (dist <= reach)] = "ice"
    return biomes


def classifyBiomes(elevation, moisture, temperature, iceNoise):
    e, m, t = elevation, moisture, temperature

    conditions = [
        e < deepOceanMax,
        e < oceanMax,
        e < coastMax,
        (e > snowPeakMin) | ((e > mountainMin) & (t < coldMax)),
        e > mountainMin,
        t < coldMax,
        (t > hotMin) & (m < desertMoistureMax),
        (m > swampMoistureMin) & (t > 0.4) & (e < swampMaxElevation),
        (m > forestMoistureMin) & (e > deepForestElevMin),
        m > forestMoistureMin,
    ]
    choices = [
        "deep_ocean",
        "ocean",
        "coast",
        "mountain_snow",
        "mountain",
        "snowy_land",
        "desert",
        "swamp",
        "deep_forest",
        "forest",
    ]

    biomes = np.select(conditions, choices, default="plains").astype(object)

    biomes = removeSpecks(biomes)

    return applyIce(biomes, elevation, iceNoise)
