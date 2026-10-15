# ESNZ DataHub access

The supplied `hirds.csv` is catalogue metadata: 2,305 rows, including 144 Auckland
regional grid products. It has durations/ARI/region/URLs but no site rainfall
depth or intensity values. It cannot be supplied as a hyetograph. The regional
grids describe 2,000 m products, distinct from a custom point rainfall table.

Use [the official HIRDS ordering guide](https://data.niwa.co.nz/blogs/how-to/articles/get-hirds-tables)
to select the confirmed property's WGS84 latitude/longitude, name the dataset,
declare the actual purpose, review licence/terms and any price, and complete the
order. Find the downloadable point table in My Order Products. The terrain studio
shows the exact confirmed WGS84 coordinates for this step. Do not substitute a
nearby rain gauge or regional bounding-box centroid for the property.

The [official DataHub API](https://data.niwa.co.nz/pages/datahub-api-information)
uses `X-Customer-ID` and a Bearer API key from the account sidebar. This is an
order-file download API; no documented point-table generation endpoint was found
in that API page. Both private settings are saved in `.env`:

```dotenv
DATAHUB_CUSTOMER_ID=
DATAHUB_API_KEY=
```

Implemented commands, using inherited private settings or local `.env`:

```bash
floodtwin hirds-inspect --csv hirds.csv
floodtwin hirds-files
floodtwin hirds-download --id YOUR_APPROVED_ORDER_FILE_ID
```

The list call uses the documented API endpoint and prints file metadata/pagination
without signed URLs. Downloads are bounded, saved under ignored `data/raw/rainfall`,
hashed and retain provenance without saving signed query tokens. The actual API
test returned HTTP 404 with **NO_ORDERS_FOUND**, so no rainfall file was downloaded.
The Customer ID/key reached the account API, but an approved order is still needed.
No purchase or licence acknowledgment was performed on the user's behalf.

After download, verify that the table matches the site, units, HIRDS version,
current/future climate and intended ARI/AEP. Select event duration and a justified
temporal pattern, with areal-reduction guidance where applicable. A DDF/IDF table
is not itself a time series. Real design-storm integration remains gated on that
review; the studio's editable uniform rain is explicitly an exploratory assumption.
Never publish the actual `.env`, key, signed download URLs or account output.
