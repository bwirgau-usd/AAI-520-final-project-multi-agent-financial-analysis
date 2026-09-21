# Data-source adapters

Each external provider has an isolated package containing its authentication,
request, response-parsing, and provider-specific error-handling logic.

The rest of the application should access provider data through the modules in
`src/tools/`. This boundary keeps agents and workflows independent of any one
vendor and allows a provider to be replaced without rewriting the analysis
logic.

Yahoo Finance is the initial source. SEC EDGAR, FRED, NewsAPI, and Alpha
Vantage are scaffolded for later integration.

