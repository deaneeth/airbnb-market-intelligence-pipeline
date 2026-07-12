# EDA Business Interpretations

City: Amsterdam  
Snapshot date: 2026-06-15

These notes are written as plain-English interpretations for the generated EDA charts. They are intended to sit under or near the figures in the final report after manual review.

## Price Distribution

The raw price chart shows why price cannot be discussed using simple averages alone. Most listings sit in a much lower price band, while a small number of very expensive listings stretch the right tail. The log-price chart makes the main market pattern easier to see, so later comparisons should use medians, quartiles, or log price rather than treating the raw price distribution as balanced.

## Price by Room Type

Room type is one of the clearest price separators in the data. Entire homes or apartments have the highest median price at 331.00, private rooms are much lower at 172.33, hotel rooms sit between them at 227.50, and shared rooms are the budget end at 52.00. For a host, this means the biggest pricing gap is not a small neighbourhood adjustment; it is the difference between selling a whole-place stay and a room-based stay.

## Price by Property Type

The property-type chart adds more detail inside the room-type story. Houseboats, entire homes, lofts, townhouses, and condos sit at the high end, while room-based property types are generally lower. This suggests that Amsterdam visitors pay a clear premium for distinctive or self-contained stays, especially where the listing offers privacy or a recognisable Amsterdam experience.

## Price by Neighbourhood

De Pijp - Rivierenbuurt, Zuid, and De Baarsjes - Oud-West have the highest median prices among neighbourhoods with enough price-usable listings. The difference is not only about centrality: some high-priced areas are lifestyle or residential districts rather than only the historic core. For pricing strategy, neighbourhood should be treated as a real market segment, not just a map label.

## Host Portfolio Concentration

Most hosts have only one listing: 8,509 of 9,104 hosts are single-listing hosts. Hosts with two or more listings exist, but the top 10 hosts account for only 1.67% of listings. The market is therefore broad and fragmented, with some professional activity but not dominated by a small number of mega-hosts.

## Listing Count per Host

The log-scale host count view confirms that multi-listing hosts form a long tail. A small number of hosts manage many listings, but the curve does not by itself prove a formal power-law pattern. For business interpretation, the useful point is practical: most hosts behave like small operators, while a smaller professional segment may need different pricing, compliance, or account-management treatment.

## Review Score Distribution

Review scores are heavily concentrated near the top of the 1-5 scale. The median overall rating is 4.92, and 38.65% of scored listings have a perfect 5.0 overall rating. This does not prove ratings are inflated, but it does mean review score alone may not separate listing quality very well unless paired with review count, price, location, and sub-scores.

## Review Score Subdimensions

Communication and check-in have the highest median sub-scores, while value is the weakest subdimension with a median of 4.71. That is a useful business signal: guests are generally happy with host interaction, but value-for-money is where listings are more exposed. Hosts trying to improve competitiveness may get more benefit from improving perceived value than from polishing already-strong communication.

## Monthly Availability

The availability_rate is lowest in June 2026 at 0.1742 and generally rises after that. The occupancy_proxy moves in the opposite direction because it is calculated as 1 - availability_rate. This proxy is derived from host-set availability; it is not equivalent to confirmed booked nights. Still, the pattern suggests tighter near-term supply and looser availability further into the calendar window.

## Listing Supply Map by Room Type

Entire-home listings are spread widely across Amsterdam, while private rooms are also visible across central and outer neighbourhoods. The map shows that the market is not only concentrated in the historic centre; supply is distributed across many residential districts. That matters for local policy and host strategy because neighbourhood-level competition can be intense outside the obvious tourist core.

## Property-Type Geography

The property-type geography chart shows that entire rental units and condos dominate much of the mapped supply, while distinctive categories such as houseboats and hotel rooms appear in more specific clusters. This supports a segmented view of the market: location matters, but the type of accommodation also shapes which micro-markets a listing competes in.

## Price Versus Distance to Centre

Log price generally softens as distance from the centre increases, especially for private rooms. Entire homes stay higher across most distances, which means room type still matters even after considering location. The chart should be read as an association, not a causal effect, because distance is mixed with neighbourhood, property type, listing quality, and other unobserved factors.

## Host Segment Price and Availability

Casual hosts have a higher median price at 318.00, while professional hosts have a lower median price at 200.08 and higher mean availability_rate at 0.467. The occupancy_proxy is derived from host-set availability; it is not equivalent to confirmed booked nights. A practical interpretation is that professional hosts may be operating more supply-oriented inventory with more open calendar space, while casual hosts may price higher or open fewer dates.

## Superhost Price and Score Profile

Superhost listings have a lower median price than non-superhost listings in this snapshot, but their mean review score is slightly higher. This should not be read as superhost status causing lower prices or better scores. A more defensible reading is that superhost status may reflect reliable operations and guest satisfaction, while price differences are probably also shaped by room type, location, and listing mix.

## Review Frequency Relationships

Review_frequency is a demand signal proxy only: reviews per month as reported by Inside Airbnb, not confirmed bookings. The scatterplots show many listings clustered at low review_frequency, with a few extreme high-review listings. There is no simple visual rule that higher review_frequency always means higher price or higher score. For business use, review_frequency is better treated as one signal among several, not a standalone performance measure.

## High-Review, Low-Score Listing Profile

The high-review, low-score profile is useful because it highlights listings with enough guest volume for the score signal to matter. Private rooms in Centrum-West and Centrum-Oost appear prominently in this group, with median review counts above 160 and median scores around 4.67-4.70. These listings are not necessarily bad, but they are visible enough that small quality issues could have an outsized reputation effect.

## Review Volume Trend

Review volume rises strongly over the available history, with a sharp disruption around 2020 and a recovery afterward. This should not be treated as a complete demand history because reviews are only a partial demand signal. Still, it gives useful context: the Amsterdam short-term rental market appears to have rebuilt review activity after the disruption and reached very high review volumes in the most recent period.

## Monthly Minimum-Night Policy

Minimum-night policy is stable across most of the calendar window. The median minimum stay is usually 3 nights, and the 75th percentile is usually 4 nights, with July 2026 slightly lower. This suggests minimum-night rules are not heavily seasonal in the current calendar data, at least at the broad monthly level.

## Coverage Limitations

Host-tenure charts were not generated because `host_tenure_years` has zero populated rows. Host-response-rate charts were also not generated because `host_response_rate` has zero populated rows. Event-level analysis was not attempted because no event data is present in the snapshot and no external event dataset was introduced.
