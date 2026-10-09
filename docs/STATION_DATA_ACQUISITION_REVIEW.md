# Station acquisition review after V5

## Verified access and genuine source fixture

The live XKDR India Air Quality Database API is usable immediately with its publisher-provided public demonstration credential. No user key, signup, card or private credential was used. The credential is intentionally absent from the fixture, URLs and report. Ordinary access to the landing page returned HTTP 403, but the documented API returned HTTP 200; no challenge was bypassed.

Recorded evidence: `data/samples/station_source_probe_v1.json` contains genuine unmodified response payloads, response hashes, observation time and safe URLs for:

- `/v1/stations?city=Bengaluru&format=json`: 14 station metadata records, not a guarantee of complete measurements.
- `/v1/parameters?format=json`: pollutant definitions and coverage metadata.
- `/v1/measurements?station=site_162&parameter=Ozone&parameter=CO&parameter=PM2.5&parameter=PM10&parameter=NO2&parameter=SO2&start=2024-04-01&end=2024-04-01&agg=raw&format=json&limit=150`: 144 records, six pollutants times 24 hours, `truncated=false`, BTM Layout Bengaluru CPCB.

The measurement shape is `station_id`, `parameter_name`, `unit`, `collected_at`, `value`. Timestamps are explicitly naive IST (UTC+05:30), so attach Asia/Kolkata before conversion. A separate eight-row Bapuji Nagar ozone probe exposed a missing 03:00 reading; station-hour completeness must be measured rather than presumed.

**Unit verification:** parsed fixture codepoints are U+00B5 and U+00B3: µg/m³ for five pollutants, mg/m³ for CO. Initial Windows terminal rendering displayed replacement glyphs, but the recorded JSON payload is intact. An importer must accept only explicit documented parameter-specific unit strings and reject mojibake/unknown forms. CO requires multiplication by1000 for the existing modeled runner's µg/m³ feature contract. This probe does not prove every station/year shares units.

## Acquisition route and limitations

Use the documented raw measurements API on a CPU-only hosted job, splitting 2024 into station-month (or smaller) slices. Inspect `X-Truncated`, payload `truncated`, row limits and counts; split further if truncated. Retain raw response hashes, station IDs, source attribution, units and time interpretation. Never stitch different stations into one pollutant vector. First measure duplicate keys, missing hours, six-pollutant intersections, implausible values and episode coverage. Missing pollutant target labels must not be imputed into evaluation truth.

The publisher public demo is limited to 10,000 rows per query and 2024 bulk files. Public 2024 bulk Parquet supports range reads; use hosted DuckDB if needed, not a nationwide local download. Historical multi-year access would require the publisher's free key and human Cloudflare signup; it is unnecessary for the initial 2024 support audit. This is an independently operated CPCB-derived compilation, not a direct CPCB endpoint. Its CC BY 4.0 terms require attribution to XKDR and underlying CPCB/AirNow sources. It is supplied without calibration, gap filling or regulatory/health validation. See [publisher documentation](https://airquality.xkdr.org/).

## Other sources checked

- [CPCB station list](https://cpcb.nic.in/upload/national-air-quality-index/Station_List_Of_CAAQMS.pdf) confirms named Bengaluru stations. [CPCB AQI portal](https://airquality.cpcb.gov.in/AQI_India/) exposes an AQI repository and captcha; no automated captcha path was attempted. AQI aggregates are not interchangeable with raw hourly pollutant concentrations.
- [OGD real-time AQI catalog](https://www.data.gov.in/catalog/real-time-air-quality-index) is a real-time feed; no verified historical six-pollutant hourly acquisition route was obtained here. Do not substitute latest pollutant min/max/average summaries for the historical target series.
- [OpenAQ API](https://docs.openaq.org/resources/measurements) provides original measurements and hourly averages. A live unauthenticated Bengaluru location query returned 401. Its [public S3 archive](https://docs.openaq.org/aws/about) is accessible without an account, but Bengaluru location IDs and per-location licensing/units still require discovery. Sensor metadata must be checked; gas units can be ppm rather than mass concentration.

## Separate modeled coverage expansion

[Open-Meteo's official source documentation](https://open-meteo.com/en/docs/air-quality-api) places CAMS global availability from August 2022, at 0.4 degree resolution and native three-hourly cadence. Existing V5 training begins January 2023. Therefore August–December 2022 is a concrete distinct training-only coverage audit, with frozen later diagnostics and unchanged V3 objective, if support adds useful episodes. Audit the actual returned timestamps, units, missingness and risk episode count first. Hourly API rows must not be represented as independent native hourly observations. Additional modeled history is exploratory evidence; station observations are not a prerequisite for every exploratory fit.

The preferable immediate action is the accessible 2024 station support/target audit in parallel with the unconsumed 2022 modeled training support audit. A fit follows actual measured support and a distinct preregistered hypothesis, with honest source limitations and no automatic deployment.
