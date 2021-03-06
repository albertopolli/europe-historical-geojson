import json
from io import StringIO
from itertools import product
from pathlib import Path
from typing import List

import geopandas as gpd
import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import requests_cache
import yaml
from geopandas import GeoDataFrame, GeoSeries
from matplotlib import pyplot as plt
from pandas import DataFrame
from requests import get
from shapely.geometry import MultiPolygon, Polygon
from shapely.ops import cascaded_union

requests_cache.install_cache("demo_cache")

config = lambda: yaml.safe_load(Path("mappe.yaml").read_text())
maps = lambda: config()["maps"]


def _get_europe():
    europe = config()["europe_borders"]
    eu_area = gpd.read_file(StringIO(json.dumps(europe)))
    eu_area = eu_area.set_crs("EPSG:4326")
    return eu_area




def filter_noise(shape: MultiPolygon):
    return MultiPolygon([p for p in shape if p.area > 1_010_202_521])


def togli_isolette(area, base=1):
    for i, poli in enumerate(list(area.geometry)):
        if isinstance(poli, MultiPolygon):
            area.geometry[i] = MultiPolygon([k for k in poli if k.area > base])
    return area


def togli_isolette_2(area, base):
    print(id(area))
    entity = getattr(area, "geometry", area)
    for i, poli in enumerate(entity):
        if isinstance(poli, MultiPolygon):
            print(i, max(k.area for k in poli))
            entity[i] = MultiPolygon([k for k in poli if k.area > base])
        if isinstance(poli, Polygon):
            print("poli", i, poli.area)


def get_polygons(label):
    """
    Si collega ad internet e scarica i poligoni associati alla label.
    """
    coord_type = 3857
    coord_type = 4326
    base = "https://gisco-services.ec.europa.eu/distribution/v2"

    if isinstance(label, int):
        return get(
            f"http://polygons.openstreetmap.fr/get_geojson.py?id={label}&params=0"
        )

    if label.startswith("http"):
        return get(label)

    for db, year in (("nuts", 2021), ("countries", 2020)):
        ret = get(
            f"{base}/{db}/distribution/{label}-region-10m-{coord_type}-{year}.geojson"
        )
        if ret.status_code == 200:
            break
        print(f"cannot find {ret.url}")
    return ret


def get_axis():
    fig, ax = plt.subplots(1, 1)
    fig.set_size_inches(10, 10)
    return fig, ax


def get_area(label) -> GeoSeries:
    return gpd.read_file(get_polygons(label).content.decode())


def join_areas(areas: List) -> GeoSeries:
    get_areas = [get_area(label) for label in areas]
    ret = GeoSeries(cascaded_union([x.geometry[0] for x in get_areas]))
    # ret = ret.set_crs("EPSG:4326")
    return ret  # .to_crs("EPSG:4326")


def get_state(state_label) -> dict:
    territori = maps()[state_label]["territori"]
    return {k: join_areas(v) for k, v in territori.items()}


def get_state_df(state_label) -> GeoDataFrame:
    # get_state returns EPSG4236
    territori = list(get_state(state_label).items())
    n, s = territori[0]

    df = DataFrame({"name": [n]})
    ret = gpd.GeoDataFrame(df, geometry=s)
    for n, s in territori[1:]:
        ret = ret.append(gpd.GeoDataFrame(DataFrame({"name": [n]}), geometry=s))

    ret = ret.set_crs("EPSG:4326")
    return ret


def render(gdfm, facecolor1="blue", facecolor2="blue", ax=None):
    empire = gdfm

    print(empire)
    for region_name in empire.name:
        region = empire[empire.name == region_name]
        print(region, region_name)

        togli_isolette(region, 0.2)
        empire[empire.name == region_name] = region

        try:
            points = (
                region.intersection(_get_europe())
                .to_crs(epsg=3857)
                .representative_point()
            )
            for p in points:
                plt.annotate(
                    text=region_name,
                    xy=p.coords[:][0],
                    horizontalalignment="left",
                    verticalalignment="baseline",
                    fontsize=11,
                    fontname="Times New Roman",
                )
        except:
            pass

    # Limit the map to EU and convert to 3857 to improve printing.
    empire = gdfm.intersection(_get_europe())
    empire = empire.to_crs(epsg=3857)

    # Draw borders with different colors.
    empire.plot(ax=ax, edgecolor="white", facecolor=facecolor2, linewidth=2)
    empire.plot(ax=ax, edgecolor="white", facecolor=facecolor1, linewidth=0, alpha=0.5)


def render_state(state_label, ax):
    state_area = get_state_df(state_label)
    color_config = maps()[state_label]["config"]
    render(state_area, ax=ax, **color_config)
    return state_area


def cm2inch(*tupl):
    inch = 2.54
    if isinstance(tupl[0], tuple):
        return tuple(i / inch for i in tupl[0])
    else:
        return tuple(i / inch for i in tupl)




def titola(df):
    points = df.to_crs(epsg=3857).representative_point()
    for p in points:
        plt.annotate(
            s="Ciao", xy=p.coords[:][0],
        )


def render_board():
    from mpl_toolkits.axes_grid1 import make_axes_locatable

    fig, risk_board = plt.subplots(1, 1)
    plt.tight_layout(pad=1)
    fig.set_size_inches(cm2inch(29 * 2, 21 * 2), forward=True)
    fig.set_dpi(300)
    eu = _get_europe().to_crs(epsg=3857)
    eu.plot(ax=risk_board, facecolor="lightblue")
    countries = (
        "Italia",
        "France",
        "Asburgici",
        "Ottomano",
        "Regno Unito",
        "Indipendenti",
        "Prussia",
        "Russia",
    )
    from multiprocessing.pool import ThreadPool as Pool
    from functools import partial

    with Pool(processes=10) as pool:
        pool.map(partial(render_state, ax=risk_board), countries)
    pool.join()
    fig.savefig("/tmp/risk.png", dpi=300)


if __name__ == "__main__":
    render_board()
