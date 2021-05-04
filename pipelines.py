# To add a new cell, type '# %%'
# To add a new markdown cell, type '# %% [markdown]'
# %%
import os
import argparse
import shutil

from wbe_odm import odm
from wbe_odm import utilities
from wbe_odm.odm_mappers import mcgill_mapper, csv_mapper,\
    ledevoir_mapper, modeleau_mapper, vdq_mapper

import json
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from config import *


def str2bool(arg):
    value = arg.lower()
    if value in STR_YES:
        return True
    elif value in STR_NO:
        return False
    else:
        raise argparse.ArgumentError('Unrecognized boolean value.')


def make_point_feature(row, props_to_add):
    return {
        "type": "Feature",
        "geometry": {
            "type": "Point",
            "coordinates": [row["geoLong"], row["geoLat"]],
            },
        "properties": {
            k: row[k] for k in props_to_add
        }
    }


def get_latest_sample_date(df):
    if len(df) == 0:
        return pd.NaT
    df["plotDate"] = utilities.get_plot_datetime(df)
    df = df.sort_values(by="plotDate")
    return df.iloc[-1, df.columns.get_loc("plotDate")]


def get_cm_to_plot(samples, thresh_n):
    # the type to plot depends on:
    # 1) What is the latest collection method for samples at that site
    # 2) How many samples of that cm there are
    possible_cms = ["ps", "cp", "grb"]
    last_dates = []
    n_samples = []
    for cm in possible_cms:
        samples_of_type = samples.loc[
            samples["Sample.collection"].str.contains(cm)
        ]
        n_samples.append(len(samples_of_type))
        last_dates.append(get_latest_sample_date(samples_of_type))
    series = [pd.Series(x) for x in [possible_cms, n_samples, last_dates]]
    types = pd.concat(series, axis=1)
    types.columns = ["type", "n", "last_date"]
    types = types.sort_values("last_date", ascending=True)

    # if there is no colleciton method that has enough
    # samples to satisfy the threshold, that condition is moot
    types = types.loc[~types["last_date"].isna()]
    if len(types.loc[types["n"] >= thresh_n]) == 0:
        thresh_n = 0
    types = types.loc[types["n"] >= thresh_n]
    if len(types) == 0:
        return None
    return types.iloc[-1, types.columns.get_loc("type")]


def get_samples_for_site(site_id, df):
    sample_filter1 = df["Sample.siteID"].str.lower() == site_id.lower()
    return df.loc[sample_filter1].copy()


def get_viral_measures(df):
    cols_to_remove = []
    for col in df.columns:
        l_col = col.lower()
        cond1 = "wwmeasure" in l_col
        cond2 = "covn2" in l_col or 'npmmov' in l_col
        cond3 = "gc" in l_col
        if (cond1 and cond2 and cond3) or "plotdate" in l_col:
            continue
        cols_to_remove.append(col)
    df.drop(columns=cols_to_remove, inplace=True)
    return df


def get_site_list(sites):
    return sites["siteID"].dropna().unique().to_list()


def get_last_sunday(date):
    if date is None:
        date = pd.to_datetime("01-01-2020")
    date = date.to_pydatetime()
    offset = (date.weekday() - 6) % 7
    return date - timedelta(days=offset)


def combine_viral_cols(viral):
    sars = []
    pmmov = []
    for col in viral.columns:
        if "plotDate" in col:
            continue
        _, virus, _, _, _ = col.lower().split("_")
        if "cov" in virus:
            sars.append(col)
        elif "pmmov" in virus:
            pmmov.append(col)
    for name, ls in zip(["sars", "pmmov"], [sars, pmmov]):
        viral[name] = viral[ls].mean(axis=1)
    viral.drop(columns=sars+pmmov, inplace=True)
    return viral


def get_samples_in_interval(samples, dateStart, dateEnd):
    samples
    if pd.isna(dateStart) and pd.isna(dateEnd):
        return samples
    elif pd.isna(dateStart):
        return samples.loc[samples["Sample.plotDate"] <= dateEnd]
    elif pd.isna(dateEnd):
        return samples.loc[samples["Sample.plotDate"] >= dateStart]
    return samples.loc[
        samples["Sample.plotDate"] >= dateStart &
        samples["Sample.plotDate"] <= dateEnd]


def get_samples_to_plot(samples, cm):
    if pd.isna(cm):
        return None
    return samples.loc[
        samples["Sample.collection"].str.contains(cm)]


def get_viral_timeseries(samples):
    viral = get_viral_measures(samples)
    viral = combine_viral_cols(viral)
    viral["norm"] = normalize_by_pmmv(viral)
    return viral


def normalize_by_pmmv(df):
    div = df["sars"] / df["pmmov"]
    div = div.replace([np.inf], np.nan)
    return div[~div.isna()]


def build_empty_color_ts(date_range):
    df = pd.DataFrame(date_range)
    df.columns = ["last_sunday"]
    df["norm"] = np.nan
    return df


def get_n_bins(series, all_colors):
    max_len = len(all_colors)
    len_not_null = len(series[~series.isna()])
    if len_not_null == 0:
        return None
    elif len_not_null < max_len:
        return len_not_null
    return max_len


def get_color_ts(samples, dateStart=DEFAULT_START_DATE, dateEnd=None):
    dateStart = pd.to_datetime(dateStart)
    weekly = None
    if samples is not None:
        viral = get_viral_timeseries(samples)
        if viral is not None:
            viral["last_sunday"] = viral["Sample.plotDate"].apply(
                get_last_sunday)
            weekly = viral.resample("W", on="last_sunday").mean()

    date_range_start = get_last_sunday(dateStart)
    if dateEnd is None:
        dateEnd = pd.to_datetime("now")
    date_range = pd.date_range(start=date_range_start, end=dateEnd, freq="W")
    result = pd.DataFrame(date_range)
    result.columns = ["date"]
    result.sort_values("date", inplace=True)

    if weekly is None:
        weekly = build_empty_color_ts(date_range)
    weekly.sort_values("last_sunday", inplace=True)
    result = pd.merge(
        result,
        weekly,
        left_on="date",
        right_on="last_sunday",
        how="left")

    n_bins = get_n_bins(result["norm"], COLORS)
    if n_bins is None:
        result["signal_strength"] = 0
    elif n_bins == 1:
        result["signal_strength"] = 1
    else:
        result["signal_strength"] = pd.cut(
            result["norm"],
            n_bins,
            labels=range(1, n_bins+1))
    result["signal_strength"] = result["signal_strength"].astype("str")
    result.loc[result["signal_strength"].isna(), "signal_strength"] = "0"
    result["date"] = result["date"].dt.strftime("%Y-%m-%d")
    result.set_index("date", inplace=True)
    return pd.Series(result["signal_strength"]).to_dict()


def get_website_type(types):
    site_types = {
        "wwtpmuc": "Station de traitement des eaux usées municipale pour égouts combinés",  # noqa
        "pstat": "Station de pompage",
        "ltcf": "Établissement de soins de longue durée",
        "airpln": "Avion",
        "corFcil": "Prison",
        "school": "École",
        "hosptl": "Hôpital",
        "shelter": "Refuge",
        "swgTrck": "Camion de vidange",
        "uCampus": "Campus universitaire",
        "mSwrPpl": "Collecteur d'égouts",
        "holdTnk": "Bassin de stockage",
        "retPond": "Bassin de rétention",
        "wwtpMuS": "Station de traitement des eaux usées municipales pour égouts sanitaires seulement",  # noqa
        "wwtpInd": "Station de traitement des eaux usées industrielle",
        "lagoon": "Système de lagunage pour traitement des eaux usées",
        "septTnk": "Fosse septique.",
        "river": "Rivière",
        "lake": "Lac",
        "estuary": "Estuaire",
        "sea": "Mer",
        "ocean": "Océan",
    }
    return types.str.lower().map(site_types)


def get_municipality(ids):
    municipalities = {
        "qc": "Québec",
        "mtl": "Montréal",
        "lvl": "Laval",
        "tr": "Trois-Rivières",
        "dr": "Drummondville",
        "vc": "Victoriaville",
        "riki": "Rimouski",
        "rdl": "Rivière-du-Loup",
        "stak": "Saint-Alexandre-de-Kamouraska",
        "3p": "Trois-Pistoles",
        "mtn": "Matane"
    }
    city_id = ids.str.lower().apply(lambda x: x.split("_")[0])
    return city_id.map(municipalities)


def website_collection_method(cm):
    collection = {
        "cp": {
            "french": "Composite",
            "english": "Composite"},
        "grb": {
            "french": "Ponctuel",
            "english": "Grab"},
        "ps": {
            "french": "Passif",
            "english": "Passive"
        }
    }
    return cm.map(collection)


def get_site_geoJSON(
        sites,
        combined,
        site_output_dir,
        site_name,
        dateStart=None,
        dateEnd=None,):
    combined["Sample.plotDate"] = utilities.get_plot_datetime(combined)
    sites["samples_for_site"] = sites.apply(
        lambda row: get_samples_for_site(row["siteID"], combined),
        axis=1)
    sites["samples_in_range"] = sites.apply(
        lambda row: get_samples_in_interval(
            row["samples_for_site"], dateStart, dateEnd),
        axis=1)
    sites["collection_method"] = sites.apply(
        lambda row: get_cm_to_plot(
            row["samples_in_range"], thresh_n=7),
        axis=1)
    sites["samples_to_plot"] = sites.apply(
        lambda row: get_samples_to_plot(
            row["samples_in_range"], row["collection_method"]),
        axis=1)
    sites["date_color"] = sites.apply(
        lambda row: get_color_ts(
            row["samples_to_plot"], dateStart, dateEnd),
        axis=1)

    sites["clean_type"] = get_website_type(sites["type"])
    sites["municipality"] = get_municipality(sites["siteID"])
    sites["collection_method"] = website_collection_method(
        sites["collection_method"])
    cols_to_keep = [
        "siteID",
        "name",
        "description",
        "clean_type",
        "polygonID",
        "municipality",
        "collection_method",
        "date_color"]
    sites.fillna("", inplace=True)
    sites["features"] = sites.apply(
        lambda row: make_point_feature(row, cols_to_keep), axis=1)
    point_list = list(sites["features"])
    js = {
        "type": "FeatureCollection",
        "features": point_list
    }
    path = os.path.join(site_output_dir, site_name)
    with open(path, "w") as f:
        f.write(json.dumps(js, indent=4))
    return


def build_polygon_geoJSON(polygons, output_dir, name, types=None):
    for col in ["pop", "link"]:
        if col in polygons.columns:
            polygons.drop(columns=[col], inplace=True)
    polys = store.get_geoJSON(types=types)
    path = os.path.join(output_dir, name)
    with open(path, "w") as f:
        f.write(json.dumps(polys, indent=4))


if __name__ == "__main__":
    # Arguments
    parser = argparse.ArgumentParser()
    parser.add_argument('-cty', '--cities', nargs="+", default=["qc", "mtl"], help='Cities to load data from')  # noqa
    parser.add_argument('-st', '--sitetypes', nargs="+", default=["wwtp"], help='Types of sites to parse')  # noqa
    parser.add_argument('-cphd', '--publichealth', type=str2bool, default=True, help='Include public health data (default=True')  # noqa
    parser.add_argument('-re', '--reload', type=str2bool, default=False, help='Reload from raw sources (default=False) instead of from the current csv')  # noqa
    parser.add_argument('-gd', '--generate', type=str2bool, default=False, help='Generate datasets for machine learning (default=False)')  # noqa
    parser.add_argument('-web', '--website', type=str2bool, default=False, help='build geojson files for website (default=False)')  # noqa

    args = parser.parse_args()

    cities = args.cities
    sitetypes = args.sitetypes
    publichealth = args.publichealth
    generate = args.generate
    website = args.website
    reload = args.reload
    generate = args.generate

    if not os.path.exists(CSV_FOLDER):
        raise ValueError(
            "CSV folder does not exist. Please modify config file.")

    store = odm.Odm()

    if reload:
        if "qc" in cities:
            print("Importing data from Québec City...")
            print("Importing viral data from Québec City...")
            qc_lab = mcgill_mapper.McGillMapper()
            qc_lab.read(QC_VIRUS_DATA, STATIC_DATA, QC_VIRUS_SHEET_NAME, QC_VIRUS_LAB)  # noqa
            store.append_from(qc_lab)
            print("Importing Wastewater lab data from Québec City...")
            modeleau = modeleau_mapper.ModelEauMapper()
            modeleau.read(QC_LAB_DATA, QC_SHEET_NAME, lab_id=QC_LAB)
            store.append_from(modeleau)
            print("Importing Quebec city sensor data...")
            files = os.listdir(os.path.join(DATA_FOLDER, QC_CITY_SENSOR_FOLDER))
            for file in files:
                vdq_sensors = vdq_mapper.VdQSensorsMapper()
                print("Parsing file " + file + "...")
                vdq_sensors.read(file)
                store.append_from(vdq_sensors)
            print("Importing Quebec city lab data...")
            files = os.listdir(os.path.join(DATA_FOLDER, QC_CITY_PLANT_FOLDER))
            for file in files:
                vdq_plant = vdq_mapper.VdQPlantMapper()
                print("Parsing file " + file + "...")
                vdq_plant.read(file)
                store.append_from(vdq_plant)


        if "mtl" in cities:
            print("Importing data from Montreal...")
            mcgill_lab = mcgill_mapper.McGillMapper()
            poly_lab = mcgill_mapper.McGillMapper()
            print("Importing viral data from McGill...")
            mcgill_lab.read(MTL_LAB_DATA, STATIC_DATA, MTL_MCGILL_SHEET_NAME, MCGILL_VIRUS_LAB)  # noqa
            print("Importing viral data from Poly...")
            poly_lab.read(MTL_LAB_DATA, STATIC_DATA, MTL_POLY_SHEET_NAME, POLY_VIRUS_LAB)  # noqa
            store.append_from(mcgill_lab)
            store.append_from(poly_lab)

        if publichealth:
            print("Importing case data from Le Devoir...")
            ledevoir = ledevoir_mapper.LeDevoirMapper()
            ledevoir.read()
            store.append_from(ledevoir)

        print("Removing older dataset...")
        for root, dirs, files in os.walk(CSV_FOLDER):
            for f in files:
                os.unlink(os.path.join(root, f))
            for d in dirs:
                shutil.rmtree(os.path.join(root, d))

        print("Saving dataset...")
        prefix = datetime.now().strftime("%Y-%m-%d")
        store.to_csv(CSV_FOLDER, prefix)
        print(f"Saved to folder {CSV_FOLDER} with prefix \"{prefix}\"")

        print("Saving combined dataset...")
        combined = store.combine_per_sample()
        combined_path = os.path.join(CSV_FOLDER, "combined.csv")
        combined = combined[~combined.index.duplicated(keep='first')]
        combined.to_csv(combined_path)
        print(f"Saved Combined dataset to folder {CSV_FOLDER}.")

    print("Reading data back from csv...")
    store = odm.Odm()
    from_csv = csv_mapper.CsvMapper()
    from_csv.read(CSV_FOLDER)
    store.append_from(from_csv)
    print("Combining dataset into wide table...")
    combined = store.combine_per_sample()
    combined = combined[~combined.index.duplicated(keep='first')]

    if website:
        print("Generating website files...")
        sites = store.site
        sites["siteID"] = sites["siteID"].str.lower()
        sites = sites.drop_duplicates(subset=["siteID"], keep="first").copy()

        site_type_filt = sites["type"].str.contains('|'.join(sitetypes))
        sites = sites.loc[site_type_filt]

        city_filt = sites["siteID"].str.contains('|'.join(cities))
        sites = sites.loc[city_filt]

        js = get_site_geoJSON(
            sites,
            combined,
            SITE_OUTPUT_DIR,
            SITE_NAME,
            dateStart=None,
            dateEnd=None)

        polygons = store.polygon
        polygons["polygonID"] = polygons["polygonID"].str.lower()
        polygons = polygons.drop_duplicates(
            subset=["polygonID"], keep="first").copy()

        build_polygon_geoJSON(
            polygons, POLYGON_OUTPUT_DIR, POLY_NAME, POLYS_TO_EXTRACT)

    if generate:
        print("Generating ML Dataset...")