import base64
import io
import json

import dash
import dash_core_components as dcc
import dash_html_components as html
import pandas as pd
import plotly.express as px
import plotly.io as pio
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate
from wbe_odm import odm
from wbe_odm import visualization_helpers

OdmEncoder = odm.OdmEncoder
decode_object = odm.decode_object
Odm = odm.Odm

pd.options.display.max_columns = None
pio.templates.default = "plotly_white"


# If I find a way to use the icons provided
# by the mapbox api, these would be the icons for each site type
site_icons = {
    # https://labs.mapbox.com/maki-icons/
    "wwtpMuC": "industry",
    "pStat": "watermill",
    "airPln": "airport",
    "corFcil": "prison",
    "school": "school",
    "hosptl": "hospital-JP",
    "ltcf": "defibrillator",
    "swgTrck": "bus",
    "uCampus": "college",
    "mSwrPpl": "cemetery-JP",
    "holdTnk": "square-stroked",
    "retPond": "wetland",
    "wwtpMuS": "industry",
    "wwtpInd": "industry",
    "lagoon": "wetland",
    "septTnk": "square",
    "river": "waterfall",
    "lake": "water",
    "estuary": "water",
    "sea": "water",
    "ocean": "water",
    "other": "marker",
}


def get_id_from_name_geojson(geo, name):
    features = geo["features"]
    for feature in features:
        if feature["properties"]["name"] == name:
            return feature["properties"]["polygonID"]
    return None


def poly_name_from_agg(
    odm_instance: Odm,
    df: pd.DataFrame
        ) -> pd.Series:
    poly_df = odm_instance.polygon
    df["Polygon.name"] = ""
    df.reset_index(inplace=True)
    for i, row in df.iterrows():
        poly_id = row["Site.polygonID"]
        poly_name = poly_df.loc[poly_df["polygonID"] == poly_id, "name"]
        df.iloc[i, df.columns.get_loc("Polygon.name")] = poly_name
    return df["Polygon.name"]


def draw_map(sample_data, odm_instance, geo):
    map_height = 800
    map_center = visualization_helpers.get_map_center(geo)
    zoom_level = visualization_helpers.get_zoom_level(geo, map_height)
    sample_data["Polygon.name"] = poly_name_from_agg(
        odm_instance, sample_data
    )
    sample_data["Site.icon"] = sample_data["Site.type"].apply(
        lambda x: site_icons.get(x, "marker")
    )
    site_data = sample_data[[
        "Site.name",
        "Site.type",
        "Site.geoLat",
        "Site.geoLong",
        "Site.icon"
    ]].drop_duplicates()
    print(site_data["Site.icon"].to_list())
    # Choropleth layer for sewersheds
    fig = px.choropleth_mapbox(
        sample_data,
        geojson=geo,
        locations="Site.polygonID",
        featureidkey="properties.polygonID",
        custom_data=["Polygon.name"],
        hover_name="Polygon.name",
        color="Polygon.name",
        center=map_center,
        opacity=0.5,
        mapbox_style="open-street-map",
        zoom=zoom_level,

    )

    fig.add_scattermapbox(
        below="",
        name="Sampling Sites",
        lat=site_data["Site.geoLat"],
        lon=site_data["Site.geoLong"],
        customdata=site_data["Site.name"],
        mode="markers",
        marker=dict(
            size=20,
            symbol="circle",
            color="black",
            opacity=1,
        ),
        hoverinfo="text",
        text=site_data["Site.name"],
        showlegend=True,

    )
    fig.update_layout(
        clickmode="event+select",
        height=map_height,
        legend_orientation="h",
        legend_yanchor="top",
        legend_xanchor="left"
    )
    return fig


def get_timeseries_names(names):
    return [name for name in names if "date" in name.lower()]


def get_values_names(names):
    return [name for name in names if "value" in name.lower()]


# Build App
app = dash.Dash(__name__)  # JupyterDash(__name__)
application = app.server
app.layout = html.Div(
    [
        dcc.Store(id='odm-store'),
        dcc.Store(id='geo-store'),
        dcc.Store(id="plot-1-store"),
        dcc.Store(id="sample-store"),

        html.H1(
            "Data exploration - COVID Wastewater data",
            style={"textAlign": "center"}
        ),
        html.Br(),
        html.Div(
            [
                html.Div(
                    [
                        dcc.Upload(
                            id='upload-data',
                            children=html.Button(
                                'Upload Excel Template File',
                                id='upload-button',
                                className='button-primary',
                            ),
                            multiple=False,
                            style={'float': 'middle'}
                        ),
                        html.Br(),
                        html.Br(),
                        html.Br(),
                        dcc.Graph(id='timeseries-1'),
                    ],
                    style={
                        'width': '45%',
                        'display': 'inlineBlock',
                        'float': 'left',
                    },
                ),
                html.Div(
                    [
                        html.Div(
                            [
                                html.Label("Y-Axis"),
                                html.Br(),
                                dcc.Dropdown(
                                    id="y-dropdown-1",
                                ),
                            ],
                            style={
                                'width': '45%',
                                'display': 'inlineBlock',
                                'float': 'right'
                            }
                        ),
                        html.Div(
                            [
                                html.Label("X-Axis"),
                                html.Br(),
                                dcc.Dropdown(
                                    id="x-dropdown-1",
                                ),
                            ],
                            style={
                                'width': '45%',
                                'display': 'inlineBlock',
                                'float': 'left'
                            }
                        ),
                        html.Br(),
                        html.Br(),
                        html.Br(),
                        html.Br(),

                        dcc.Graph(id='map-1'),
                    ],
                    style={
                        'width': '45%',
                        'display': 'inlineBlock',
                        'float': 'right'
                    }
                ),
            ]
        ),
    ]
)


def parse_contents(contents, filename):
    _, content_string = contents.split(',')
    decoded = base64.b64decode(content_string)
    odm_instance = Odm()
    try:
        if 'csv' in filename:
            raise NotImplementedError(
                "Cannot accept .csv files at the moment."
            )
        elif 'xls' in filename:
            # Assume that the user uploaded an excel file
            # TODO: Should validate here
            odm_instance.load_from_excel(io.BytesIO(decoded))
    except Exception as e:
        return html.Div([
            f'There was an error processing this file: {e}'
        ])
    return odm_instance


# Define callback to parse the uploaded file(s)
@app.callback(
    Output('odm-store', 'data'),
    [Input('upload-data', 'contents')],
    [State('upload-data', 'filename')]
)
def read_uploaded_excel(contents, filename):
    if contents is None:
        raise PreventUpdate
    odm_instance = parse_contents(contents, filename)

    return json.dumps(odm_instance, indent=4, cls=OdmEncoder)


@app.callback(
    [Output("sample-store", "data"),
     Output("geo-store", "data")],
    Input('odm-store', 'data'))
def map_from_samples(odm_data):
    if not odm_data:
        raise PreventUpdate
    odm_instance = json.loads(odm_data, object_hook=decode_object)

    samples = odm_instance.combine_per_sample()
    geo = odm_instance.get_geoJSON()
    return samples.to_json(date_format='iso'), geo


@app.callback(
    Output("map-1", "figure"),
    Input('sample-store', 'data'),
    [State('geo-store', 'data'),
     State("odm-store", "data")])
def combine_per_samples(samples, geo, odm_data):
    if None in [samples, geo, odm_data]:
        raise PreventUpdate
    odm_instance = json.loads(odm_data, object_hook=decode_object)
    samples = pd.read_json(samples)
    return draw_map(samples, odm_instance, geo)


# Define callback to update graphs
@app.callback(
    Output('timeseries-1', 'figure'),
    [Input("x-dropdown-1", "value"),
     Input("y-dropdown-1", "value"),
     Input("plot-1-store", "data")])
def time_series_1(x_col, y_col, data):
    if y_col is None:
        return px.scatter()
    df = pd.read_json(data)

    return px.scatter(
        df, x=x_col, y=y_col,
        title=f"{y_col} over time"
    )


@app.callback(
    Output("plot-1-store", "data"),
    [Input('map-1', 'clickData'),
     Input('sample-store', 'data')],
    State("geo-store", "data"))
def filter_by_clicked_location(click_data, samples_data, geo):
    if None in [click_data, samples_data, geo]:
        raise PreventUpdate
    samples = pd.read_json(samples_data)
    point = click_data["points"][0]
    print("point data", point)
    custom_data = point.get("customdata", None)
    if custom_data is None:
        filt = True
    else:
        if isinstance(custom_data, list):
            place_name = point["customdata"][0]
            poly_id = get_id_from_name_geojson(geo, place_name)
            filt = samples["Site.polygonID"] == poly_id
        elif isinstance(custom_data, str):
            place_name = custom_data
            filt = samples["Site.name"] == place_name
    return samples.loc[filt] \
        .to_json(date_format='iso')


def get_series(df):
    return [col for col in df.columns if "date" not in col]


def get_times(df):
    return [col for col in df.columns if "date" in col]


def clean_labels_y(cols):
    clean_labels = {}
    for col in cols:
        table_name = col.split(".")[0]
        if table_name == "WWMeasure":
            _, param, unit, _, _ = col.split(".")[1:]
            unit = unit.replace("-", "/")
            clean_label = f"{table_name} {param} ({unit})"

        if table_name == "Sample":
            clean_label = col
        if table_name == "SiteMeasure":
            param, unit, _, _ = col.split(".")[1:]
            unit = unit.replace("-", "/")
            clean_label = f"{table_name} {param} ({unit})"

        clean_labels.add(clean_label)
    return clean_labels


def clean_labels_x(cols):
    clean_labels = {}
    for col in cols:
        fields = col.split(".")
        for field in fields:
            if "date" in field:
                clean_labels.add(field)
    return clean_labels


@app.callback(
    Output('y-dropdown-1', 'options'),
    Input('plot-1-store', 'data'))
def update_dropdown_y1(plot_data):
    if plot_data is None:
        raise PreventUpdate
    df = pd.read_json(plot_data)

    series_y = get_series(df)
    cols_y = series_y.columns.tolist()
    labels_y = clean_labels_y(cols_y)
    y_options = [
        {'label': label, 'value': col}
        for label, col in zip(labels_y, cols_y)]
    return y_options


@app.callback(
    Output('x-dropdown-1', 'options'),
    [Input('plot-1-store', 'data'),
     Input('y-dropdown-1', 'value')])
def update_dropdown_x1(plot_data, y_col):
    if None in [plot_data, y_col]:
        raise PreventUpdate
    df = pd.read_json(plot_data)

    series_x = get_times(df)
    cols_x = series_x.columns.tolist()
    labels_x = clean_labels_x(cols_x, "date")
    x_options = [
        {'label': label, 'value': col}
        for label, col in zip(labels_x, cols_x)]
    return x_options


if __name__ == "__main__":
    app.run_server(debug=True)  # inline