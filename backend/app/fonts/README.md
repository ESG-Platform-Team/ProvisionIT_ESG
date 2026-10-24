Fonts used by the PDF report, converted from the Latin subsets already vendored
in `frontend/vendor/fonts` so the report matches the interface.

- Inter, SIL Open Font License 1.1
- Archivo, SIL Open Font License 1.1
- IBM Plex Mono, SIL Open Font License 1.1

The subsets cover Latin-1 and common punctuation. Characters outside that range
are transliterated by `report._clean` before rendering, so a subscript in CO₂
prints as CO2 rather than as a missing glyph.
