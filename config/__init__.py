import os
COLORS = {
    0: {
        "french": "Pas de données",
        "english": "No Data",
        "color": None},
    1: {
        "french": "Très faible",
        "english": "Very Low",
        "color": "#6da06f"},
    2: {
        "french": "Faible",
        "english": "Low",
        "color": "#b6e9d1"},
    3: {
        "french": "Moyennement élevé",
        "english": "Somewhat high",
        "color": "#ffbb43"},
    4: {
        "french": "Élevé",
        "english": "High",
        "color": "#ff8652"},
    5: {
        "french": "Très élevé",
        "english": "Very high",
        "color": "#c13525"},
}


STR_YES = [
    'y',
    'yes',
    't',
    'true'
]

STR_NO = [
    'n',
    'no',
    'f',
    'false'
]


DATA_FOLDER = "/Users/jeandavidt/OneDrive - Université Laval/COVID/Latest Data"  # noqa
CSV_FOLDER = "/Users/jeandavidt/OneDrive - Université Laval/COVID/Latest Data/odm_csv"  # noqa
STATIC_DATA = os.path.join(DATA_FOLDER, "CentrEAU-COVID_Static_Data.xlsx")  # noqa

QC_LAB_DATA = os.path.join(DATA_FOLDER, "CentrEau-COVID_Resultats_Quebec_final.xlsx")  # noqa
QC_SHEET_NAME = "QC Data Daily Samples (McGill)"
QC_VIRUS_LAB = "frigon_lab"

MTL_LAB_DATA = os.path.join(DATA_FOLDER, "CentrEau-COVID_Resultats_Montreal_final.xlsx")  # noqa
MTL_POLY_SHEET_NAME = "Mtl Data Daily Samples (Poly)"
MTL_MCGILL_SHEET_NAME = "Mtl Data Daily Samples (McGill)"
MCGILL_VIRUS_LAB = "frigon_lab"
POLY_VIRUS_LAB = "dorner_lab"

POLYGON_OUTPUT_DIR = "/Users/jeandavidt/OneDrive - Université Laval/COVID/Website geo"
POLY_NAME = "polygons.geojson"
POLYS_TO_EXTRACT = ["swrCat"]

SITE_OUTPUT_DIR = "/Users/jeandavidt/OneDrive - Université Laval/COVID/Website geo"
SITE_NAME = "sites.geojson"