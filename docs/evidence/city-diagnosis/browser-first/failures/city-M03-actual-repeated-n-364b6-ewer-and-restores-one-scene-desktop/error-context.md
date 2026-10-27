# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: city.spec.ts >> M03 actual repeated navigation destroys the old viewer and restores one scene
- Location: tests/browser/city.spec.ts:136:1

# Error details

```
Test timeout of 45000ms exceeded.
```

# Page snapshot

```yaml
- generic [ref=e1]:
  - generic [ref=e2]:
    - complementary "Workspace navigation" [ref=e3]:
      - link [ref=e4] [cursor=pointer]:
        - /url: "#overview"
      - navigation "Main navigation" [ref=e12]:
        - button "Overview" [ref=e13] [cursor=pointer]
        - button "Geospatial Data" [ref=e19] [cursor=pointer]
        - button "City Explorer" [ref=e22] [cursor=pointer]
        - button "Scenario Studio" [ref=e25] [cursor=pointer]
        - button "Simulation Laboratory" [ref=e30] [cursor=pointer]
        - button "Traffic Intelligence" [ref=e33] [cursor=pointer]
        - button "AI Command Center" [ref=e38] [cursor=pointer]
        - button "Analytics" [ref=e50] [cursor=pointer]
        - button "System Status" [ref=e53] [cursor=pointer]
        - button "Settings" [ref=e56] [cursor=pointer]
    - main [ref=e61]:
      - generic [ref=e62]:
        - generic [ref=e63]:
          - generic [ref=e64]: Workspace
          - strong [ref=e67]: City Explorer
        - generic [ref=e68]:
          - generic [ref=e69]: LOCAL DEVELOPMENT
          - generic [ref=e71]: M03
      - region "Dubai 3D digital twin" [ref=e75]:
        - generic [ref=e76]:
          - generic [ref=e77]:
            - paragraph [ref=e78]: DOWNTOWN DUBAI / BUSINESS BAY
            - heading "Dubai digital twin" [level=2] [ref=e79]
          - generic [ref=e80]: DEVELOPMENT DATA
        - generic [ref=e86]:
          - generic [ref=e87]:
            - text: Study region
            - combobox "3D study region" [disabled] [ref=e88]:
              - option "No study regions" [selected]
          - generic [ref=e89]:
            - text: Network version
            - combobox "3D network version" [disabled] [ref=e90]:
              - option "No network versions" [selected]
          - generic [ref=e91]:
            - generic "Show synthetic fixtures instead of imported geographic datasets" [ref=e92]:
              - checkbox "Development datasets" [checked] [active] [ref=e93]
              - generic [ref=e96]: Development datasets
            - button "Enter fullscreen" [ref=e97] [cursor=pointer]
            - button "Layers" [ref=e103] [cursor=pointer]
            - button "Show feature inspector" [ref=e110] [cursor=pointer]
            - button "Refresh geographic data" [ref=e114] [cursor=pointer]
        - alert [ref=e120]:
          - generic [ref=e123]:
            - strong [ref=e124]: Some geographic data could not load
            - paragraph [ref=e125]: Geographic service unavailable (HTTP 503). Retry the request.
          - button "Retry data" [ref=e126] [cursor=pointer]
        - generic "Geographic data provenance" [ref=e127]:
          - generic [ref=e128]: GEOGRAPHIC BASEMAP — OpenStreetMap
          - generic [ref=e129]: 3D BUILDINGS — OSM source-height context · partial coverage
          - generic [ref=e130]: SYNTHETIC TRAFFIC — CLI smoke only; no viewer playback
          - generic [ref=e131]: LIVE TRAFFIC — Not connected
          - generic [ref=e132]: INFERRED SIGNALS — Not field verified
        - generic [ref=e134]:
          - generic [ref=e135]:
            - generic:
              - generic: CESIUM · WGS84
              - generic: GEOGRAPHIC CONTEXT
            - generic "Interactive 3D geographic globe" [ref=e137]:
              - generic [ref=e143]:
                - link [ref=e146] [cursor=pointer]:
                  - /url: https://cesium.com/
                  - img "Cesium ion" [ref=e147]
                - generic [ref=e148]:
                  - generic [ref=e149]:
                    - text: ©
                    - link "OpenStreetMap contributors" [ref=e150] [cursor=pointer]:
                      - /url: https://www.openstreetmap.org/copyright
                    - text: · ODbL
                  - text: •Made with Natural Earth · public domain
            - status:
              - generic: "0"
              - text: roads ·
              - generic: "0"
              - text: intersections rendered
            - generic "Map legend":
              - generic: Road centerlines
              - generic: Intersection
              - generic: OSM signal tag · unverified
              - generic: Selected feature
          - generic "Camera controls" [ref=e151]:
            - generic [ref=e152]:
              - button "Dubai overview" [ref=e153] [cursor=pointer]
              - button "Downtown Dubai" [ref=e154] [cursor=pointer]
              - button "Business Bay" [ref=e155] [cursor=pointer]
            - generic [ref=e156]:
              - button "Zoom to study region" [disabled] [ref=e157]
              - button "Zoom to selected feature" [disabled] [ref=e164]
              - button "Top-down view" [ref=e170] [cursor=pointer]
              - button "Perspective view" [ref=e173] [cursor=pointer]
              - button "Zoom in" [ref=e177] [cursor=pointer]
              - button "Zoom out" [ref=e181] [cursor=pointer]
              - button "Reset camera" [ref=e185] [cursor=pointer]
          - generic "Camera position indicator" [ref=e189]:
            - generic [ref=e193]: 55.27440° E · 25.18167° N · 2,458 m altitude
            - generic [ref=e194]: EPSG:4326 · longitude, latitude
        - group [ref=e195]:
          - generic "Network & source details No network selected" [ref=e196] [cursor=pointer]:
            - text: Network & source details
            - generic [ref=e201]: No network selected
        - paragraph [ref=e204]:
          - generic [ref=e210]:
            - text: Local OpenStreetMap cartography over Natural Earth reference; no satellite imagery.
            - strong [ref=e211]: "Cesium ion building tiles unavailable:"
            - text: set CESIUM_ION_PUBLIC_TOKEN. Ellipsoid terrain; OSM tagged-height buildings cover only part of the source area.
  - alert [ref=e212]
```