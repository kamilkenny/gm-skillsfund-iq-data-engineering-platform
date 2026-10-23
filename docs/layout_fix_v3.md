# GM SkillsFund IQ dashboard layout fix v3

Corrects the overlapping panels visible in the Funding Assurance screenshot.

- Funding, borough and source registers put explanatory notes **above** the data table.
- Table controls are enclosed in a width-constrained, flow-positioned wrapper.
- Donut percentage labels move inside the chart boundary; the chart reserves its own height.
- The provider allocation chart reserves additional space for its x-axis title.
- Existing SQL queries, source data and managed identity are unchanged.
- Compatible with the original v2 Dash package and the forthcoming automation package; the Data Assurance page checks whether pipeline history support is present before calling it.

Upload this ZIP to Cloud Shell and extract it at repository root. Then run unit tests, commit, and deploy the dashboard as before. When applying the separate automation ZIP, apply this layout patch afterwards to keep the UI fix.
