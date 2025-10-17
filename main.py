# pip install geopandas
# pip install matplot
# pip install geopandas matplotlib folium

import geopandas as gpd
import pandas as pd
import folium
import re

# --- ASETUKSET ---
GEOJSON = "kuntarajat-2018-raw.geojson"   # vaihda tarvittaessa oman tiedoston nimeen
CSV     = "vakiluku.csv"                  # laita tähän äsken tehty CSV
OUTPUT  = "suomen_kunnat.html"


# --- APUTOIMINNOT ---
def normalize(name: str) -> str:
    """Nimien normalisointi yhdistämistä varten (skandit -> perus, välit yhtenäistetään)."""
    if not isinstance(name, str):
        return ""
    s = name.strip().casefold()
    s = s.replace("ä", "a").replace("ö", "o").replace("å", "a")
    s = re.sub(r"\s+", " ", s)
    return s

# Alias-korjaukset muutamille ongelmanimille (vasen = CSV:ssä, oikea = GeoJSONissa NAMEFIN)
ALIASES = {
    "pedersoren kunta": "pedersore",   # GeoJSONissa yleensä "Pedersöre"
}

# --- 1) LUE KUNTARAJAT ---
gdf_raw = gpd.read_file(GEOJSON)

# Kunnannimi-sarake: tässä aineistossa yleensä NAMEFIN
name_col = "NAMEFIN" if "NAMEFIN" in gdf_raw.columns else (
    "Kunta" if "Kunta" in gdf_raw.columns else (
        "name" if "name" in gdf_raw.columns else None
    )
)
if not name_col:
    raise ValueError(f"Kunnan nimi -saraketta ei löytynyt. Sarakkeet: {list(gdf_raw.columns)}")
print(f"Käytetään kunnannimi-saraketta: {name_col}")

# --- 2) PINTA-ALAT (km²) TM35 ---
gdf_metric = gdf_raw.to_crs(epsg=3067).copy()
gdf_metric["Pinta_ala_km2"] = gdf_metric.geometry.area / 1e6

# --- 3) WGS84 versio Foliumia varten ---
gdf = gdf_metric.to_crs(epsg=4326).copy()

# --- 4) LUE VÄKILUVUT JA YHDISTÄ ---
vak = pd.read_csv(CSV)

# Normalisoi avaimet, käytä alias-korjauksia CSV-puolelle
vak_key = vak["Kunta"].map(normalize).replace(ALIASES)
gdf_key = gdf[name_col].map(normalize)

vak2 = pd.DataFrame({"__key": vak_key, "Väkiluku": vak["Väkiluku"]})
gdf["__key"] = gdf_key

gdf = gdf.merge(vak2, on="__key", how="left").drop(columns="__key")

# Raportoi ne kunnat, joilta puuttui väkiluku
puuttuvat = gdf[gdf["Väkiluku"].isna()][name_col].tolist()
if puuttuvat:
    print("Huom. Kuntakartta on vuodelta 2018 ja asukasluvut ovat vuodelta 2025, joten seuraavat kunnat ovat yhdistyneet ja niiden tietoja ei ole saatavilla.")
    for n in puuttuvat[:20]:  # rajataan listaa, jos pitkä
        print(" -", n)
    if len(puuttuvat) > 20:
        print(f"... ja {len(puuttuvat)-20} muuta")

# --- 5) FOLIUM-KARTTA ---
m = folium.Map(location=[64.5, 26.0], zoom_start=5)

# Kuntarajat GeoJSONina
folium.GeoJson(
    gdf[["geometry"]],
    name="Kuntarajat"
).add_to(m)

# Markkereiden paikat: käytetään representative_point(), joka on varmasti polygonin sisällä
points = gdf.geometry.representative_point()

for (_, row), pt in zip(gdf.iterrows(), points):
    kunta = str(row[name_col])
    ala = row["Pinta_ala_km2"]
    vakiluku = row.get("Väkiluku")
    vak_txt = f"{int(vakiluku):,}".replace(",", " ") if pd.notna(vakiluku) else "–"

    popup = folium.Popup(
        f"<b>{kunta}</b><br>Pinta-ala: {ala:.1f} km²<br>Väkiluku: {vak_txt}",
        max_width=320
    )
    folium.Marker(
        location=[pt.y, pt.x],
        popup=popup,
        icon=folium.Icon(color="blue", icon="info-sign")
    ).add_to(m)

folium.LayerControl().add_to(m)
m.save(OUTPUT)
print(f"OK → {OUTPUT}")
