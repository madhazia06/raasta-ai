# Arbitrary Place -> Nearest Stop -> Map Setup

The app now accepts Lahore places that are not present in `data/stops.csv`.

## Flow
1. If the typed place matches a RAASTA stop, its dataset coordinates are used.
2. Otherwise the place is geocoded in Lahore.
3. RAASTA finds the nearest stop from the existing stop dataset.
4. The existing route engine calculates the bus journey.
5. Walking segments are calculated for start -> boarding stop and drop-off stop -> destination.
6. An interactive OpenStreetMap map displays the complete journey.

## Install
```powershell
py -m pip install -r requirements.txt
```

## Google Maps key (recommended)
The app works without a key using OpenStreetMap geocoding and estimated walking paths.
For better landmark matching and real walking directions, create a Google Maps Platform key and enable:

- Geocoding API
- Directions API

Copy:

`.streamlit/secrets.toml.example`

to:

`.streamlit/secrets.toml`

Then add:

```toml
GOOGLE_MAPS_API_KEY = "YOUR_REAL_KEY"
```

Do not commit `.streamlit/secrets.toml`; it is already ignored by `.gitignore`.

## Run
```powershell
py -m streamlit run app.py
```

Try a trip using a place that is not a transit stop, for example `Butt Chowk`, together with another Lahore destination.
