# V7.9 Environmental Evidence

Environmental provider data is supporting observation or forecast data. It is
cached locally and is never a personal-data authority. JSON and SQLite
authority markers are unchanged by this feature.

The normalized contract separates `air.temp_f` from `water.temp_f`. Open-Meteo
`temperature_2m` is air temperature; it is never presented as a measured water
temperature. Water temperature remains `unknown` until a direct user or agency
observation is available.

V7.9.0 adds the provider-neutral contract, conservative provenance, solar
dayparts, direct-observation precedence, and an ignored runtime cache under
`instance/cache/environment/`. Provider adapters for USGS and NOAA are staged
for later subreleases. The dashboard continues to use its existing weather
fallback when a provider is unavailable.

Configuration planned for provider subreleases:

```text
AI_USGS_ENABLED=1
AI_USGS_API_KEY=
AI_USGS_CACHE_SECONDS=900
AI_NWPS_ENABLED=1
AI_NWPS_NWM_ENABLED=0
AI_NWPS_HEFS_ENABLED=0
```
