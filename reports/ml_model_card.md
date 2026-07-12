# Nightly Price Prediction Model Card

- **City**: amsterdam
- **Snapshot date**: 2026-06-15
- **Target**: `price_log`, the natural log of parsed nightly listing price.
- **Population**: 6377 price-usable listing rows before the train/test split.
- **Split**: reproducible listing-level train/test split with 5101 train rows and 1276 test rows.
- **Success metrics**: MAE and RMSE on log and original price scales; MAPE is reported only where true price is at least 1.
- **Leakage policy**: excludes identifiers, raw price, parsed price, log price as features, revenue_proxy, occupancy_proxy, availability_rate, and review_frequency.
- **Features**: room type, property type, bedrooms, bathrooms, accommodates, capped minimum nights, long-stay flag, distance to centre, superhost flag, neighbourhood, amenity count, and six amenity flags.
- **Amenity flags**: wifi, kitchen, washer, air conditioning, dedicated workspace, and free parking.
- **Interactions**: none included; the experiment keeps feature engineering limited and interpretable.
- **Best test MAE on original price scale**: 89.94 from Histogram gradient boosting regressor.
- **Important caveat**: feature importance is predictive association, not causal evidence.
- **Representation risk**: neighbourhood and room-type imbalance can make error uneven across groups; see the error-slice tables before using results in a report.
- **Production warning**: one Amsterdam snapshot is not enough to claim production readiness or future generalisation.
