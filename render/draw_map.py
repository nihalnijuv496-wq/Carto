import os

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import ListedColormap
from matplotlib.image import BboxImage
from matplotlib.legend_handler import HandlerBase
from matplotlib.lines import Line2D
from matplotlib.offsetbox import AnnotationBbox, OffsetImage
from matplotlib.patches import Patch
from matplotlib.transforms import Bbox, TransformedBbox

from generator.terrain import biomeColors
from models.settlement import Village

iconDir = os.path.join(os.path.dirname(__file__), "..", "assets", "icons")
settlementIconDir = os.path.join(iconDir, "settlements")
reasonIconDir = os.path.join(iconDir, "reasons")

settlementIconZoom = 0.02
reasonIconZoom = 0.02

biomeOrder = [
    "deep_ocean",
    "ocean",
    "ice",
    "coast",
    "plains",
    "forest",
    "deep_forest",
    "desert",
    "swamp",
    "mountain",
    "mountain_snow",
    "snowy_land",
]
biomeToIndex = {name: i for i, name in enumerate(biomeOrder)}

settlementStyles = {
    "village": {"marker": "o", "color": "#d32f2f", "size": 30},
    "city": {"marker": "s", "color": "#d32f2f", "size": 60},
    "witch_hut": {"marker": "^", "color": "#8e44ad", "size": 50},
    "school": {"marker": "P", "color": "#2980b9", "size": 55},
    "dungeon": {"marker": "X", "color": "#4a0404", "size": 55},
    "palace": {"marker": "*", "color": "#ffd700", "size": 90},
    "portal": {"marker": "D", "color": "#00e5ff", "size": 55},
}

foundingReasonStyles = {
    "mining": {"marker": "v", "color": "#6d4c41"},
    "market": {"marker": "<", "color": "#f1c40f"},
    "crops": {"marker": "p", "color": "#9ccc65"},
}

foundingReasonOffset = 15

iconCache = {}


def loadIcon(filepath):
    if filepath in iconCache:
        return iconCache[filepath]

    if not os.path.isfile(filepath):
        iconCache[filepath] = None
        return None

    image = plt.imread(filepath)
    iconCache[filepath] = image
    return image


def drawIconOrFallback(ax, x, y, imagePath, zoom, fallbackStyle, fallbackSize, zorder):
    image = loadIcon(imagePath)

    if image is not None:
        imageBox = OffsetImage(image, zoom=zoom, resample=False)
        annotation = AnnotationBbox(
            imageBox, (x, y), frameon=False, pad=0, zorder=zorder
        )
        ax.add_artist(annotation)
    else:
        ax.scatter(
            x,
            y,
            marker=fallbackStyle["marker"],
            s=fallbackSize,
            c=fallbackStyle["color"],
            edgecolors="black",
            zorder=zorder,
        )


class LegendIcon:
    def __init__(self, image):
        self.image = image


class HandlerLegendIcon(HandlerBase):
    def __init__(self, scale=1.4, **kwargs):
        super().__init__(**kwargs)
        self.scale = scale

    def create_artists(
        self, legend, origHandle, xdescent, ydescent, width, height, fontsize, trans
    ):
        size = height * self.scale
        x0 = xdescent + (width - size) / 2
        y0 = ydescent - (size - height) / 2

        bbox = TransformedBbox(Bbox.from_bounds(x0, y0, size, size), trans)
        image = BboxImage(bbox, interpolation="nearest")
        image.set_data(origHandle.image)
        return [image]


def biomesToIndexGrid(biomes):
    names, inverse = np.unique(biomes, return_inverse=True)
    mapping = np.array([biomeToIndex[name] for name in names])
    return mapping[inverse].reshape(biomes.shape)


def buildFigure(world):
    indexGrid = biomesToIndexGrid(world.biomes)
    cmap = ListedColormap([biomeColors[name] for name in biomeOrder])

    fig, ax = plt.subplots(figsize=(8, 6))
    ax.imshow(indexGrid, cmap=cmap, vmin=0, vmax=len(biomeOrder) - 1, origin="upper")

    seenTypes = set()
    seenReasons = set()

    for settlement in world.settlements:
        iconPath = os.path.join(settlementIconDir, f"{settlement.settlementType}.png")
        fallback = settlementStyles.get(
            settlement.settlementType, {"marker": "o", "color": "#d32f2f"}
        )
        drawIconOrFallback(
            ax,
            settlement.x,
            settlement.y,
            iconPath,
            settlementIconZoom,
            fallback,
            fallback.get("size", 30),
            zorder=3,
        )

        ax.annotate(
            settlement.name,
            (settlement.x, settlement.y),
            fontsize=7,
            color="white",
            xytext=(3, 3),
            textcoords="offset points",
            zorder=5,
        )
        seenTypes.add(settlement.settlementType)

        if (
            isinstance(settlement, Village)
            and settlement.foundingReason in foundingReasonStyles
        ):
            reasonIconPath = os.path.join(
                reasonIconDir, f"{settlement.foundingReason}.png"
            )
            reasonFallback = foundingReasonStyles[settlement.foundingReason]
            drawIconOrFallback(
                ax,
                settlement.x + foundingReasonOffset,
                settlement.y - foundingReasonOffset,
                reasonIconPath,
                reasonIconZoom,
                reasonFallback,
                70,
                zorder=4,
            )
            seenReasons.add(settlement.foundingReason)

    legendHandles = [Patch(color=biomeColors[name]) for name in biomeOrder]
    legendLabels = [name.title() for name in biomeOrder]

    for settlementType in sorted(seenTypes):
        icon = loadIcon(os.path.join(settlementIconDir, f"{settlementType}.png"))
        if icon is not None:
            legendHandles.append(LegendIcon(icon))
        else:
            style = settlementStyles.get(
                settlementType, {"marker": "o", "color": "#d32f2f"}
            )
            legendHandles.append(
                Line2D(
                    [0],
                    [0],
                    marker=style["marker"],
                    color="w",
                    markerfacecolor=style["color"],
                    markeredgecolor="black",
                    markersize=8,
                    linestyle="none",
                )
            )
        legendLabels.append(settlementType.replace("_", " ").title())

    for reason in sorted(seenReasons):
        icon = loadIcon(os.path.join(reasonIconDir, f"{reason}.png"))
        if icon is not None:
            legendHandles.append(LegendIcon(icon))
        else:
            style = foundingReasonStyles[reason]
            legendHandles.append(
                Line2D(
                    [0],
                    [0],
                    marker=style["marker"],
                    color=style["color"],
                    markersize=8,
                    linestyle="none",
                )
            )
        legendLabels.append(f"Village: {reason}")

    ax.legend(
        handles=legendHandles,
        labels=legendLabels,
        handler_map={LegendIcon: HandlerLegendIcon(scale=3.0)},
        handlelength=2.5,
        borderpad=1.2,
        labelspacing=1.0,
        handletextpad=1.0,
        loc="upper left",
        bbox_to_anchor=(1.02, 1),
        fontsize=8,
    )

    ax.set_title(f"{world.name} (seed={world.seed})")
    ax.set_xticks([])
    ax.set_yticks([])
    fig.tight_layout()
    return fig


def showMap(world):
    fig = buildFigure(world)
    plt.show()
    plt.close(fig)


def saveMap(world, filepath):
    fig = buildFigure(world)
    fig.savefig(filepath, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return filepath
