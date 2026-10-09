# Reopened target, data and algorithm reviews

Three read-only research agents completed this round after the user's continued-research instruction. Their findings led to distinct implementations, not another unchanged neural fit.

## Target reviewer

The historical hourly breakpoint task differs from the app's conservative hourly/trailing policy. At t+6, complete 24-hour means combine 18 known and six predicted concentrations; 8-hour means combine two known and six predictions. Existing saved neural outputs contain h6 only, so learned period-mean forecasts cannot be invented from them. The new hosted CPU audit completed as fc-01M4FQ5AR38P77DCWRDAZ9N2M3, app ap-EYjomUeIBrjTquMy5bYdOv. Its source-pinned result verified every historical target and the complete-window identity. See ../eval/raw/pollutant_target_contract_v1_summary.md. Changing targets changes support, not historical model accuracy.

## Data reviewer

The live public XKDR CPCB-derived archive supplied 14 Bengaluru station records and 144 real BTM Layout pollutant measurements for one day. A genuine fixture is retained. Explicit UTF-8 decoding confirmed valid µg/m³ and mg/m³ strings; the initial apparent corruption came from terminal decoding. Timestamps are IST, and coverage must be measured. An initial 2024 station audit can proceed without a private key. Independently, additional 2022 modeled training coverage may be investigated; station observations are not a prerequisite for every exploratory fit. See STATION_DATA_ACQUISITION_REVIEW.md.

## Algorithm reviewer

On 1,411 exactly shared development origins, a frozen 24-hour Ridge comparator improved ozone Poor+ MAE from 21.861 to 19.056, episode onsets from 5 to 13 of 28, and Very Poor misses from 22 to 18 of 22. Poor+ misses rose from 62 to 64 and false alarms from 15 to 23. A fixed ozone-only hybrid had the same risk scores but lower overall accuracy than full Ridge. The existing Ridge and V3 training sets differ by 24 boundary origins, so these adaptive descriptive results justify a full-origin fixed linear comparator rather than claiming an accepted improvement. See ../eval/raw/linear_ozone_complementarity_v1.md.

## Decision

Preregister one fixed full-origin 24-hour Ridge study with alpha10, the existing training-only preprocessing and weight2. Compare every origin and target against frozen V3; keep its gate unchanged. Do not sweep architecture, alpha, thresholds, blend weights or diagnostic cutoffs. Station support acquisition proceeds as a separate read-only data study, with raw responses retained remotely and December station labels excluded from discovery. Continue after actual results and explicit reviews of remaining evidence gaps; no automatic deployment or global maximum claim.
