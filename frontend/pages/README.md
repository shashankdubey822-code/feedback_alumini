# Page Modules

This folder groups the dashboard into page-specific source files.

- `overview-page.js` - KPI cards, filters, AI insights, and overview rendering.
- `charts-page.js` - Chart destruction, chart rendering, and chart options.
- `ai-insights-page.js` - AI insight section wrapper.
- `nlp-page.js` - NLP deep analysis, sentiment, and keyword rendering.
- `speakers-page.js` - Speaker stats section.
- `departments-page.js` - Department comparison section.

The live Hugging Face app still uses the existing SPA runtime, so these files are safe to keep alongside the deployed build as a cleaner source layout.
