# Data Dictionary

This document records the selected Amsterdam Inside Airbnb snapshot schema before transformation.
Observed row counts, null rates, ranges, and sample values come from the live source files configured in `configs/cities.yml`.
Free-text, name, URL, image, permit, and review-comment samples are redacted in this committed document to avoid storing personal or listing-specific content.

## Snapshot

| Field | Value |
|---|---|
| City | Amsterdam |
| Country / region | North Holland, The Netherlands |
| Snapshot date | 2026-06-15 |
| Source | Inside Airbnb official download page and data dictionary |

## Business Entities and Relationships

| Entity | Grain | Primary Key | Foreign Keys | Notes |
|---|---|---|---|---|
| listing | accommodation offer observed in the selected snapshot | `id` / canonical `listing_id` | `host_id`, `neighbourhood_cleansed` | Main analytical entity. |
| host | account associated with one or more listings | `host_id` | none | Host fields are repeated on listing rows. |
| calendar record | listing-date availability observation | (`listing_id`, `date`) | `listing_id` -> listing | `available` is host-set availability, not confirmed bookings. |
| review | public review record or listing-level review date summary | detailed `id`; summary (`listing_id`, `date`) | `listing_id` -> listing | Review submission is optional. |
| neighbourhood | geographic grouping used by Inside Airbnb | `neighbourhood` | referenced by listing neighbourhood fields | GeoJSON supplies polygon geometry. |

## Source Files

| File Key | Configured URL | Business Grain |
|---|---|---|
| `listings_detailed` | `https://data.insideairbnb.com/the-netherlands/north-holland/amsterdam/2026-06-15/data/listings.csv.gz` | one row per listing in the detailed snapshot |
| `listings_summary` | `https://data.insideairbnb.com/the-netherlands/north-holland/amsterdam/2026-06-15/visualisations/listings.csv` | one row per listing in the summary snapshot |
| `calendar` | `https://data.insideairbnb.com/the-netherlands/north-holland/amsterdam/2026-06-15/data/calendar.csv.gz` | one row per listing-date calendar observation |
| `reviews_detailed` | `https://data.insideairbnb.com/the-netherlands/north-holland/amsterdam/2026-06-15/data/reviews.csv.gz` | one row per public review record |
| `reviews_summary` | `https://data.insideairbnb.com/the-netherlands/north-holland/amsterdam/2026-06-15/visualisations/reviews.csv` | one row per listing review date in the summary file |
| `neighbourhoods` | `https://data.insideairbnb.com/the-netherlands/north-holland/amsterdam/2026-06-15/visualisations/neighbourhoods.csv` | one row per source neighbourhood label |
| `neighbourhoods_geojson` | `https://data.insideairbnb.com/the-netherlands/north-holland/amsterdam/2026-06-15/visualisations/neighbourhoods.geojson` | one feature per neighbourhood polygon or multipolygon |

## Column Dictionary

### `listings_detailed`

- **Source row count inspected**: 10,369
- **Business grain**: one row per listing in the detailed snapshot

| Source Column | Canonical Name | Observed Type | Null Rate | Range / Values | Sample Values | Grain | Interpretation | Notes |
|---|---|---|---:|---|---|---|---|---|
| `id` | listing_id when used as listing key | int64 | 0.00% | 28871 to 1708158632781004544 | 28871; 29051; 44129 | one row per listing in the detailed snapshot | Airbnb's unique identifier for the listing | Official type: integer |
| `listing_url` | unchanged unless documented in transformation | str | 0.00% | 20+ observed values | [withheld: free-text, name, URL, or permit field] | one row per listing in the detailed snapshot | Not defined in official dictionary. | Official type: text; calculated by source; sample redacted before commit |
| `scrape_id` | unchanged unless documented in transformation | int64 | 0.00% | 20260615212022 to 20260615212022 | 20260615212022 | one row per listing in the detailed snapshot | Inside Airbnb "Scrape" this was part of | Official type: bigint; calculated by source |
| `last_scraped` | unchanged unless documented in transformation | str | 0.00% | 2026-06-15 to 2026-06-24 | 2026-06-16; 2026-06-24 | one row per listing in the detailed snapshot | UTC. The date and time this listing was "scraped". | Official type: datetime; calculated by source |
| `source` | unchanged unless documented in transformation | str | 0.00% | city scrape (5864), previous scrape (4505) | previous scrape; city scrape | one row per listing in the detailed snapshot | One of "neighbourhood search" or "previous scrape". "neighbourhood search" means that the listing was found by searching the city, while "previous scrape" means that the listing was seen in another scrape performed in the last 65 days, and the listing was confirmed to be still available on the Airbnb site. | Official type: text |
| `name` | unchanged unless documented in transformation | str | 0.00% | 20+ observed values | [withheld: free-text, name, URL, or permit field] | one row per listing in the detailed snapshot | Name of the listing | Official type: text; sample redacted before commit |
| `description` | unchanged unless documented in transformation | str | 4.34% | 19+ observed values | [withheld: free-text, name, URL, or permit field] | one row per listing in the detailed snapshot | Detailed description of the listing | Official type: text; sample redacted before commit |
| `neighborhood_overview` | unchanged unless documented in transformation | float64 | 100.00% | n/a | n/a | one row per listing in the detailed snapshot | Host's description of the neighbourhood | Official type: text; sample redacted before commit |
| `picture_url` | unchanged unless documented in transformation | str | 0.00% | 20+ observed values | [withheld: free-text, name, URL, or permit field] | one row per listing in the detailed snapshot | URL to the Airbnb hosted regular sized image for the listing | Official type: text; sample redacted before commit |
| `host_id` | host_id | int64 | 0.00% | 3592 to 1705253369814659072 | 124245; 187728; 194779 | one row per listing in the detailed snapshot | Airbnb's unique identifier for the host/user | Official type: integer |
| `host_url` | unchanged unless documented in transformation | str | 0.00% | 20+ observed values | [withheld: free-text, name, URL, or permit field] | one row per listing in the detailed snapshot | The Airbnb page for the host | Official type: text; calculated by source; sample redacted before commit |
| `host_profile_id` | unchanged unless documented in transformation | float64 | 1.37% | 1462506389112963072 to 1707865740432694272 | 1.462510208428039e+18; 1.4625121252931446e+18; 1.4625123369036503e+18 | one row per listing in the detailed snapshot | Not defined in official dictionary; documented from observed source schema. | Official type: not specified |
| `host_profile_url` | unchanged unless documented in transformation | str | 1.32% | 20+ observed values | [withheld: free-text, name, URL, or permit field] | one row per listing in the detailed snapshot | Not defined in official dictionary; documented from observed source schema. | Official type: not specified; sample redacted before commit |
| `host_name` | unchanged unless documented in transformation | str | 1.37% | 20+ observed values | [withheld: free-text, name, URL, or permit field] | one row per listing in the detailed snapshot | Name of the host. Usually just the first name(s). | Official type: text; sample redacted before commit |
| `host_since` | unchanged unless documented in transformation | float64 | 100.00% | n/a | n/a | one row per listing in the detailed snapshot | The date the host/user was created. For hosts that are Airbnb guests this could be the date they registered as a guest. | Official type: date |
| `hosts_time_as_user_years` | unchanged unless documented in transformation | float64 | 1.37% | 0 to 17 | 16.0; 15.0 | one row per listing in the detailed snapshot | Not defined in official dictionary; documented from observed source schema. | Official type: not specified |
| `hosts_time_as_user_months` | unchanged unless documented in transformation | float64 | 1.37% | 0 to 11 | 1.0; 10.0; 9.0 | one row per listing in the detailed snapshot | Not defined in official dictionary; documented from observed source schema. | Official type: not specified |
| `hosts_time_as_host_years` | unchanged unless documented in transformation | float64 | 1.37% | 0 to 15 | 15.0; 10.0 | one row per listing in the detailed snapshot | Not defined in official dictionary; documented from observed source schema. | Official type: not specified |
| `hosts_time_as_host_months` | unchanged unless documented in transformation | float64 | 1.37% | 0 to 11 | 5.0; 11.0 | one row per listing in the detailed snapshot | Not defined in official dictionary; documented from observed source schema. | Official type: not specified |
| `host_location` | unchanged unless documented in transformation | str | 13.23% | 20+ observed values | [withheld: free-text, name, URL, or permit field] | one row per listing in the detailed snapshot | The host's self reported location | Official type: text; sample redacted before commit |
| `host_about` | unchanged unless documented in transformation | str | 47.83% | 20+ observed values | [withheld: free-text, name, URL, or permit field] | one row per listing in the detailed snapshot | Description about the host | Official type: text; sample redacted before commit |
| `host_response_time` | unchanged unless documented in transformation | float64 | 100.00% | n/a | n/a | one row per listing in the detailed snapshot | Not defined in official dictionary. | Official type: not specified |
| `host_response_rate` | unchanged unless documented in transformation | float64 | 100.00% | n/a | n/a | one row per listing in the detailed snapshot | Not defined in official dictionary. | Official type: not specified |
| `host_acceptance_rate` | unchanged unless documented in transformation | float64 | 100.00% | n/a | n/a | one row per listing in the detailed snapshot | That rate at which a host accepts booking requests. | Official type: not specified |
| `host_is_superhost` | unchanged unless documented in transformation | str | 1.37% | f (8513), t (1714) | t; f | one row per listing in the detailed snapshot | Not defined in official dictionary. | Official type: boolean [t=true; f=false] |
| `host_thumbnail_url` | unchanged unless documented in transformation | float64 | 100.00% | n/a | n/a | one row per listing in the detailed snapshot | Not defined in official dictionary. | Official type: text; sample redacted before commit |
| `host_picture_url` | unchanged unless documented in transformation | str | 1.37% | 20+ observed values | [withheld: free-text, name, URL, or permit field] | one row per listing in the detailed snapshot | Not defined in official dictionary. | Official type: text; sample redacted before commit |
| `host_neighbourhood` | unchanged unless documented in transformation | float64 | 100.00% | n/a | n/a | one row per listing in the detailed snapshot | Not defined in official dictionary. | Official type: text |
| `host_listings_count` | unchanged unless documented in transformation | float64 | 1.37% | 1 to 1167 | 2.0; 6.0; 1.0 | one row per listing in the detailed snapshot | The number of listings the host has (per Airbnb unknown calculations) | Official type: text |
| `host_total_listings_count` | unchanged unless documented in transformation | float64 | 100.00% | n/a | n/a | one row per listing in the detailed snapshot | The number of listings the host has (per Airbnb unknown calculations) | Official type: text |
| `host_verifications` | unchanged unless documented in transformation | float64 | 100.00% | n/a | n/a | one row per listing in the detailed snapshot | Not defined in official dictionary. | Official type: not specified; sample redacted before commit |
| `host_has_profile_pic` | unchanged unless documented in transformation | str | 1.37% | t (10072), f (155) | t | one row per listing in the detailed snapshot | Not defined in official dictionary. | Official type: boolean [t=true; f=false] |
| `host_identity_verified` | unchanged unless documented in transformation | str | 1.37% | t (10187), f (40) | t | one row per listing in the detailed snapshot | Not defined in official dictionary. | Official type: boolean [t=true; f=false] |
| `neighbourhood` | unchanged unless documented in transformation | float64 | 100.00% | n/a | n/a | one row per listing in the detailed snapshot | Not defined in official dictionary. | Official type: text |
| `neighbourhood_cleansed` | neighbourhood_cleansed | str | 0.00% | 20+ observed values | Centrum-West; Centrum-Oost; Buitenveldert - Zuidas | one row per listing in the detailed snapshot | The neighbourhood as geocoded using the latitude and longitude against neighborhoods as defined by open or public digital shapefiles. | Official type: text; calculated by source |
| `neighbourhood_group_cleansed` | unchanged unless documented in transformation | float64 | 100.00% | n/a | n/a | one row per listing in the detailed snapshot | The neighbourhood group as geocoded using the latitude and longitude against neighborhoods as defined by open or public digital shapefiles. | Official type: text; calculated by source |
| `latitude` | unchanged unless documented in transformation | float64 | 0.00% | 52.290276216002695 to 52.4251585173962 | 52.36775; 52.36584; 52.38211 | one row per listing in the detailed snapshot | Uses the World Geodetic System (WGS84) projection for latitude and longitude. | Official type: numeric |
| `longitude` | unchanged unless documented in transformation | float64 | 0.00% | 4.75587 to 5.02815 | 4.89092; 4.89111; 4.8863 | one row per listing in the detailed snapshot | Uses the World Geodetic System (WGS84) projection for latitude and longitude. | Official type: numeric |
| `property_type` | unchanged unless documented in transformation | str | 0.00% | 20+ observed values | Private room in rental unit; Private room in condo; Entire rental unit | one row per listing in the detailed snapshot | Self selected property type. Hotels and Bed and Breakfasts are described as such by their hosts in this field | Official type: text |
| `room_type` | room_type | str | 0.00% | Entire home/apt (8489), Private room (1833), Hotel room (26), Shared room (21) | Private room; Entire home/apt | one row per listing in the detailed snapshot | [Entire home/apt\|Private room\|Shared room\|Hotel]  All homes are grouped into the following three room types:  Entire place Private room Shared room Entire place Entire places are best if you're seeking a home away from home. With an entire place, you'll have the whole space to yourself. This usually includes a bedroom, a bathroom, a kitchen, and a separate, dedicated entrance. Hosts should note in the description if they'll be on the property or not (ex: "Host occupies first floor of the home"), and provide further details on the listing.  Private rooms Private rooms are great for when you prefer a little privacy, and still value a local connection. When you book a private room, you'll have your own private room for sleeping and may share some spaces with others. You might need to walk through indoor spaces that another host or guest may occupy to get to your room.  Shared rooms Shared rooms are for when you don't mind sharing a space with others. When you book a shared room, you'll be sleeping in a space that is shared with others and share the entire space with other people. Shared rooms are popular among flexible travelers looking for new friends and budget-friendly stays. | Official type: text |
| `accommodates` | unchanged unless documented in transformation | int64 | 0.00% | 1 to 16 | 2; 4; 3 | one row per listing in the detailed snapshot | The maximum capacity of the listing | Official type: integer |
| `bathrooms` | unchanged unless documented in transformation | float64 | 47.80% | 0.5 to 17 | 1.0; 1.5; 2.0 | one row per listing in the detailed snapshot | The number of bathrooms in the listing | Official type: numeric |
| `bathrooms_text` | unchanged unless documented in transformation | str | 0.09% | 20+ observed values | 1 shared bath; 1.5 baths; 1 bath | one row per listing in the detailed snapshot | The number of bathrooms in the listing.  On the Airbnb web-site, the bathrooms field has evolved from a number to a textual description. For older scrapes, bathrooms is used. | Official type: string |
| `bedrooms` | unchanged unless documented in transformation | float64 | 11.09% | 0 to 17 | 1.0; 2.0 | one row per listing in the detailed snapshot | The number of bedrooms | Official type: integer |
| `beds` | unchanged unless documented in transformation | float64 | 44.86% | 1 to 33 | 2.0; 4.0; 1.0 | one row per listing in the detailed snapshot | The number of bed(s) | Official type: integer |
| `amenities` | unchanged unless documented in transformation | str | 0.00% | 19+ observed values | [withheld: free-text, name, URL, or permit field] | one row per listing in the detailed snapshot | Not defined in official dictionary. | Official type: json; sample redacted before commit |
| `price` | price_raw before parsing; price after cleaning | str | 38.50% | 14.7 to 11412 | $94.00; $313.67; $440.27 | one row per listing in the detailed snapshot | daily price in local currency. NOTE: the $ sign is a technical artifact of the export, please ignore it | Official type: currency |
| `price_quote_checkin_date` | unchanged unless documented in transformation | str | 37.24% | 2026-06-16 to 2027-06-11 | 2027-05-29; 2026-07-16; 2026-06-19 | one row per listing in the detailed snapshot | Not defined in official dictionary; documented from observed source schema. | Official type: not specified |
| `price_quote_checkout_date` | unchanged unless documented in transformation | str | 37.24% | 2026-06-17 to 2027-06-16 | 2027-05-31; 2026-07-19; 2026-06-21 | one row per listing in the detailed snapshot | Not defined in official dictionary; documented from observed source schema. | Official type: not specified |
| `price_quote_total_price` | unchanged unless documented in transformation | float64 | 38.50% | 31 to 57059 | 188.0; 941.0; 880.53 | one row per listing in the detailed snapshot | Not defined in official dictionary; documented from observed source schema. | Official type: not specified |
| `price_quote_price_per_night` | unchanged unless documented in transformation | float64 | 38.50% | 14.7 to 11412 | 94.0; 313.67; 440.27 | one row per listing in the detailed snapshot | Not defined in official dictionary; documented from observed source schema. | Official type: not specified |
| `price_quote_raw` | unchanged unless documented in transformation | str | 37.24% | {"quote": {"taxes": null, "currency": "EUR", "date_match": null, "service_fee":  (59), {"quote": {"taxes": null, "currency": null, "date_match": null, "service_fee": n (17) | {"quote": {"taxes": null, "currency": "EUR", "date_match": null, "service_fee":  | one row per listing in the detailed snapshot | Not defined in official dictionary; documented from observed source schema. | Official type: not specified |
| `minimum_nights` | unchanged unless documented in transformation | float64 | 0.03% | 1 to 800 | 1.0; 3.0; 2.0 | one row per listing in the detailed snapshot | minimum number of night stay for the listing (calendar rules may be different) | Official type: integer |
| `maximum_nights` | unchanged unless documented in transformation | float64 | 0.03% | 1 to 2147483647 | 730.0; 1125.0; 365.0 | one row per listing in the detailed snapshot | maximum number of night stay for the listing (calendar rules may be different) | Official type: integer |
| `minimum_minimum_nights` | unchanged unless documented in transformation | float64 | 0.03% | 1 to 800 | 1.0; 3.0; 2.0 | one row per listing in the detailed snapshot | the smallest minimum_night value from the calender (looking 365 nights in the future) | Official type: integer; calculated by source |
| `maximum_minimum_nights` | unchanged unless documented in transformation | float64 | 0.03% | 1 to 800 | 2.0; 5.0; 3.0 | one row per listing in the detailed snapshot | the largest minimum_night value from the calender (looking 365 nights in the future) | Official type: integer; calculated by source |
| `minimum_maximum_nights` | unchanged unless documented in transformation | float64 | 0.03% | 1 to 2147483647 | 730.0; 1125.0; 365.0 | one row per listing in the detailed snapshot | the smallest maximum_night value from the calender (looking 365 nights in the future) | Official type: integer; calculated by source |
| `maximum_maximum_nights` | unchanged unless documented in transformation | float64 | 0.03% | 1 to 2147483647 | 730.0; 1125.0; 365.0 | one row per listing in the detailed snapshot | the largest maximum_night value from the calender (looking 365 nights in the future) | Official type: integer; calculated by source |
| `minimum_nights_avg_ntm` | unchanged unless documented in transformation | float64 | 0.00% | 1 to 800 | 2.0; 5.0; 3.0 | one row per listing in the detailed snapshot | the average minimum_night value from the calender (looking 365 nights in the future) | Official type: numeric; calculated by source |
| `maximum_nights_avg_ntm` | unchanged unless documented in transformation | float64 | 0.00% | 1 to 2147483647 | 730.0; 1125.0; 365.0 | one row per listing in the detailed snapshot | the average maximum_night value from the calender (looking 365 nights in the future) | Official type: numeric; calculated by source |
| `calendar_updated` | unchanged unless documented in transformation | float64 | 100.00% | n/a | n/a | one row per listing in the detailed snapshot | Not defined in official dictionary. | Official type: date |
| `has_availability` | unchanged unless documented in transformation | str | 1.31% | t (10081), f (152) | t | one row per listing in the detailed snapshot | [t=true; f=false] | Official type: boolean |
| `availability_30` | unchanged unless documented in transformation | int64 | 0.00% | 0 to 30 | 1; 0; 3 | one row per listing in the detailed snapshot | avaliability_x. The availability of the listing x days in the future as determined by the calendar. Note a listing may not be available because it has been booked by a guest or blocked by the host. | Official type: integer; calculated by source |
| `availability_60` | unchanged unless documented in transformation | int64 | 0.00% | 0 to 60 | 1; 2; 3 | one row per listing in the detailed snapshot | avaliability_x. The availability of the listing x days in the future as determined by the calendar. Note a listing may not be available because it has been booked by a guest or blocked by the host. | Official type: integer; calculated by source |
| `availability_90` | unchanged unless documented in transformation | int64 | 0.00% | 0 to 90 | 1; 2; 3 | one row per listing in the detailed snapshot | avaliability_x. The availability of the listing x days in the future as determined by the calendar. Note a listing may not be available because it has been booked by a guest or blocked by the host. | Official type: integer; calculated by source |
| `availability_365` | availability_365 | int64 | 0.00% | 0 to 365 | 11; 2; 3 | one row per listing in the detailed snapshot | avaliability_x. The availability of the listing x days in the future as determined by the calendar. Note a listing may not be available because it has been booked by a guest or blocked by the host. | Official type: integer; calculated by source |
| `calendar_last_scraped` | unchanged unless documented in transformation | str | 0.00% | 2026-06-15 to 2026-06-24 | 2026-06-16; 2026-06-24 | one row per listing in the detailed snapshot | Not defined in official dictionary. | Official type: date |
| `number_of_reviews` | unchanged unless documented in transformation | int64 | 0.00% | 0 to 5603 | 799; 906; 186 | one row per listing in the detailed snapshot | The number of reviews the listing has | Official type: integer |
| `number_of_reviews_ltm` | unchanged unless documented in transformation | int64 | 0.00% | 0 to 813 | 88; 82; 5 | one row per listing in the detailed snapshot | The number of reviews the listing has (in the last 12 months) | Official type: integer; calculated by source |
| `number_of_reviews_l30d` | unchanged unless documented in transformation | int64 | 0.00% | 0 to 41 | 5; 6; 0 | one row per listing in the detailed snapshot | The number of reviews the listing has (in the last 30 days) | Official type: integer; calculated by source |
| `availability_eoy` | unchanged unless documented in transformation | int64 | 0.00% | 0 to 199 | 2; 3; 0 | one row per listing in the detailed snapshot | Not defined in official dictionary; documented from observed source schema. | Official type: not specified |
| `number_of_reviews_ly` | unchanged unless documented in transformation | int64 | 0.00% | 0 to 959 | 95; 85; 1 | one row per listing in the detailed snapshot | Not defined in official dictionary; documented from observed source schema. | Official type: not specified |
| `estimated_occupancy_l365d` | unchanged unless documented in transformation | int64 | 0.00% | 20+ observed values | 255; 39; 0 | one row per listing in the detailed snapshot | Not defined in official dictionary; documented from observed source schema. | Official type: not specified |
| `estimated_revenue_l365d` | unchanged unless documented in transformation | float64 | 38.50% | 20+ observed values | 23970.0; 12233.0; 112269.0 | one row per listing in the detailed snapshot | Not defined in official dictionary; documented from observed source schema. | Official type: not specified |
| `first_review` | unchanged unless documented in transformation | str | 9.87% | 2010-08-16 to 2026-06-18 | 2010-08-22; 2011-03-16; 2010-08-16 | one row per listing in the detailed snapshot | The date of the first/oldest review | Official type: date; calculated by source |
| `last_review` | unchanged unless documented in transformation | str | 9.87% | 2014-04-22 to 2026-06-24 | 2026-06-01; 2026-04-30; 2022-08-20 | one row per listing in the detailed snapshot | The date of the last/newest review | Official type: date; calculated by source |
| `review_scores_rating` | unchanged unless documented in transformation | float64 | 9.87% | 1 to 5 | 4.86; 4.82; 4.88 | one row per listing in the detailed snapshot | Not defined in official dictionary. | Official type: not specified |
| `review_scores_accuracy` | unchanged unless documented in transformation | float64 | 9.87% | 1 to 5 | 4.89; 4.88; 4.81 | one row per listing in the detailed snapshot | Not defined in official dictionary. | Official type: not specified |
| `review_scores_cleanliness` | unchanged unless documented in transformation | float64 | 9.88% | 1 to 5 | 4.84; 4.83; 4.88 | one row per listing in the detailed snapshot | Not defined in official dictionary. | Official type: not specified |
| `review_scores_checkin` | unchanged unless documented in transformation | float64 | 9.87% | 1 to 5 | 4.94; 4.93; 4.89 | one row per listing in the detailed snapshot | Not defined in official dictionary. | Official type: not specified |
| `review_scores_communication` | unchanged unless documented in transformation | float64 | 9.87% | 1 to 5 | 4.94; 4.93; 4.89 | one row per listing in the detailed snapshot | Not defined in official dictionary. | Official type: not specified |
| `review_scores_location` | unchanged unless documented in transformation | float64 | 9.87% | 1 to 5 | 4.93; 4.88; 4.95 | one row per listing in the detailed snapshot | Not defined in official dictionary. | Official type: not specified |
| `review_scores_value` | unchanged unless documented in transformation | float64 | 9.87% | 1 to 5 | 4.83; 4.79; 4.59 | one row per listing in the detailed snapshot | Not defined in official dictionary. | Official type: not specified |
| `license` | unchanged unless documented in transformation | str | 2.15% | 20+ observed values | [withheld: free-text, name, URL, or permit field] | one row per listing in the detailed snapshot | The licence/permit/registration number | Official type: text; sample redacted before commit |
| `instant_bookable` | unchanged unless documented in transformation | float64 | 100.00% | n/a | n/a | one row per listing in the detailed snapshot | [t=true; f=false]. Whether the guest can automatically book the listing without the host requiring to accept their booking request. An indicator of a commercial listing. | Official type: boolean |
| `calculated_host_listings_count` | unchanged unless documented in transformation | int64 | 0.00% | 1 to 24 | 2; 4; 1 | one row per listing in the detailed snapshot | The number of listings the host has in the current scrape, in the city/region geography. | Official type: integer; calculated by source |
| `calculated_host_listings_count_entire_homes` | unchanged unless documented in transformation | int64 | 0.00% | 0 to 19 | 0; 3; 1 | one row per listing in the detailed snapshot | The number of Entire home/apt listings the host has in the current scrape, in the city/region geography | Official type: integer; calculated by source |
| `calculated_host_listings_count_private_rooms` | unchanged unless documented in transformation | int64 | 0.00% | 0 to 15 | 2; 1; 0 | one row per listing in the detailed snapshot | The number of Private room listings the host has in the current scrape, in the city/region geography | Official type: integer; calculated by source |
| `calculated_host_listings_count_shared_rooms` | unchanged unless documented in transformation | int64 | 0.00% | 0 to 10 | 0 | one row per listing in the detailed snapshot | The number of Shared room listings the host has in the current scrape, in the city/region geography | Official type: integer; calculated by source |
| `reviews_per_month` | review_frequency after renaming | float64 | 9.87% | 0.01 to 44.13 | 4.15; 4.88; 0.96 | one row per listing in the detailed snapshot | The average number of reviews per month the listing has over the lifetime of the listing. Pseudocode from source: IF scrape_date - first_review <= 30 THEN number_of_reviews ELSE number_of_reviews / ((scrape_date - first_review + 1) / (365/12)) | Official type: numeric; calculated by source |

### `listings_summary`

- **Source row count inspected**: 10,465
- **Business grain**: one row per listing in the summary snapshot

| Source Column | Canonical Name | Observed Type | Null Rate | Range / Values | Sample Values | Grain | Interpretation | Notes |
|---|---|---|---:|---|---|---|---|---|
| `id` | listing_id when used as listing key | int64 | 0.00% | 28871 to 1708158632781004544 | 28871; 29051; 44129 | one row per listing in the summary snapshot | Airbnb's unique identifier for the listing | Official type: integer |
| `name` | unchanged unless documented in transformation | str | 0.00% | 20+ observed values | [withheld: free-text, name, URL, or permit field] | one row per listing in the summary snapshot | Not defined in official dictionary. | Official type: string; sample redacted before commit |
| `host_id` | host_id | float64 | 0.92% | 3592 to 1705253369814659072 | 124245.0; 187728.0; 194779.0 | one row per listing in the summary snapshot | Not defined in official dictionary. | Official type: integer |
| `host_profile_id` | unchanged unless documented in transformation | float64 | 2.23% | 1462506389112963072 to 1707865740432694272 | 1.462510208428039e+18; 1.4625121252931446e+18; 1.4625123369036503e+18 | one row per listing in the summary snapshot | Not defined in official dictionary; documented from observed source schema. | Official type: not specified |
| `host_name` | unchanged unless documented in transformation | str | 2.27% | 20+ observed values | [withheld: free-text, name, URL, or permit field] | one row per listing in the summary snapshot | Not defined in official dictionary. | Official type: string; sample redacted before commit |
| `neighbourhood_group` | unchanged unless documented in transformation | float64 | 100.00% | n/a | n/a | one row per listing in the summary snapshot | The neighbourhood group as geocoded using the latitude and longitude against neighborhoods as defined by open or public digital shapefiles. | Official type: text; calculated by source |
| `neighbourhood` | unchanged unless documented in transformation | str | 0.00% | 20+ observed values | Centrum-West; Centrum-Oost; Buitenveldert - Zuidas | one row per listing in the summary snapshot | The neighbourhood as geocoded using the latitude and longitude against neighborhoods as defined by open or public digital shapefiles. | Official type: text; calculated by source |
| `latitude` | unchanged unless documented in transformation | float64 | 0.00% | 52.290276216002695 to 52.4251585173962 | 52.36775; 52.36584; 52.38211 | one row per listing in the summary snapshot | Uses the World Geodetic System (WGS84) projection for latitude and longitude. | Official type: numeric |
| `longitude` | unchanged unless documented in transformation | float64 | 0.00% | 4.75587 to 5.02815 | 4.89092; 4.89111; 4.8863 | one row per listing in the summary snapshot | Uses the World Geodetic System (WGS84) projection for latitude and longitude. | Official type: not specified |
| `room_type` | room_type | str | 0.00% | Entire home/apt (8489), Private room (1929), Hotel room (26), Shared room (21) | Private room; Entire home/apt | one row per listing in the summary snapshot | Not defined in official dictionary. | Official type: string |
| `price` | price_raw before parsing; price after cleaning | float64 | 38.17% | 15 to 11412 | 94.0; 314.0; 440.0 | one row per listing in the summary snapshot | daily price in local currency. Note, $ sign may be used despite locale | Official type: currency |
| `minimum_nights` | unchanged unless documented in transformation | float64 | 0.03% | 1 to 800 | 1.0; 3.0; 2.0 | one row per listing in the summary snapshot | minimum number of night stay for the listing (calendar rules may be different) | Official type: integer |
| `number_of_reviews` | unchanged unless documented in transformation | int64 | 0.00% | 0 to 5603 | 799; 906; 186 | one row per listing in the summary snapshot | The number of reviews the listing has | Official type: integer |
| `last_review` | unchanged unless documented in transformation | str | 9.87% | 2014-04-22 to 2026-06-28 | 2026-06-01; 2026-04-30; 2022-08-20 | one row per listing in the summary snapshot | The date of the last/newest review | Official type: date; calculated by source |
| `reviews_per_month` | review_frequency after renaming | float64 | 9.87% | 0.01 to 44.13 | 4.15; 4.88; 0.96 | one row per listing in the summary snapshot | Not defined in official dictionary; documented from observed source schema. | Official type: not specified |
| `calculated_host_listings_count` | unchanged unless documented in transformation | float64 | 0.92% | 1 to 24 | 2.0; 4.0; 1.0 | one row per listing in the summary snapshot | The number of listings the host has in the current scrape, in the city/region geography. | Official type: integer; calculated by source |
| `availability_365` | availability_365 | int64 | 0.00% | 0 to 365 | 11; 2; 3 | one row per listing in the summary snapshot | Availability in the next 365 days as determined by the calendar. A listing may be unavailable because it has been booked by a guest or blocked by the host. | Official type: integer; calculated by source |
| `number_of_reviews_ltm` | unchanged unless documented in transformation | int64 | 0.00% | 0 to 813 | 88; 82; 5 | one row per listing in the summary snapshot | The number of reviews the listing has (in the last 12 months) | Official type: integer; calculated by source |
| `license` | unchanged unless documented in transformation | str | 3.05% | 20+ observed values | [withheld: free-text, name, URL, or permit field] | one row per listing in the summary snapshot | Not defined in official dictionary. | Official type: string; sample redacted before commit |

### `calendar`

- **Source row count inspected**: 3,819,725
- **Business grain**: one row per listing-date calendar observation

| Source Column | Canonical Name | Observed Type | Null Rate | Range / Values | Sample Values | Grain | Interpretation | Notes |
|---|---|---|---:|---|---|---|---|---|
| `listing_id` | listing_id | int64 | 0.00% | 28871 to 1708158632781004544 | 28871; 1162769; 1174506 | one row per listing-date calendar observation | Not defined in official dictionary. | Official type: not specified |
| `date` | unchanged unless documented in transformation | str | 0.00% | 2026-06-15 to 2027-06-27 | 2026-06-16; 2026-06-17; 2026-06-18 | one row per listing-date calendar observation | The date in the listing's calendar | Official type: datetime |
| `available` | unchanged unless documented in transformation | str | 0.00% | f (2820970), t (998755) | f; t | one row per listing-date calendar observation | Whether the date is available for a booking | Official type: boolean |
| `minimum_nights` | unchanged unless documented in transformation | int64 | 0.00% | 1 to 800 | 2; 4; 6 | one row per listing-date calendar observation | Minimum nights for a booking made on this day | Official type: integer |
| `maximum_nights` | unchanged unless documented in transformation | int64 | 0.00% | 1 to 2147483647 | 730; 20; 7 | one row per listing-date calendar observation | Maximum nights for a booking made on this day | Official type: integer |

### `reviews_detailed`

- **Source row count inspected**: 545,162
- **Business grain**: one row per public review record

| Source Column | Canonical Name | Observed Type | Null Rate | Range / Values | Sample Values | Grain | Interpretation | Notes |
|---|---|---|---:|---|---|---|---|---|
| `listing_id` | listing_id | int64 | 0.00% | 28871 to 1704341300366137856 | 28871; 1402541; 4043288 | one row per public review record | Not defined in official dictionary. | Official type: not specified |
| `id` | review_id | int64 | 0.00% | 79730 to 1717984606216649216 | 82539; 21518912; 26293687 | one row per public review record | Source review identifier. | Official type: not specified |
| `date` | unchanged unless documented in transformation | str | 0.00% | 2010-08-16 to 2026-06-28 | 2010-08-22; 2014-10-19; 2015-02-09 | one row per public review record | Not defined in official dictionary. | Official type: not specified |
| `reviewer_id` | unchanged unless documented in transformation | int64 | 0.00% | 1 to 1711012061390045184 | 163752; 20597737; 20543694 | one row per public review record | Not defined in official dictionary. | Official type: not specified |
| `reviewer_name` | unchanged unless documented in transformation | str | 0.00% | 24+ observed values | [withheld: free-text, name, URL, or permit field] | one row per public review record | Not defined in official dictionary. | Official type: not specified; sample redacted before commit |
| `comments` | unchanged unless documented in transformation | str | 0.01% | 26+ observed values | [withheld: free-text, name, URL, or permit field] | one row per public review record | Not defined in official dictionary. | Official type: not specified; sample redacted before commit |

### `reviews_summary`

- **Source row count inspected**: 545,162
- **Business grain**: one row per listing review date in the summary file

| Source Column | Canonical Name | Observed Type | Null Rate | Range / Values | Sample Values | Grain | Interpretation | Notes |
|---|---|---|---:|---|---|---|---|---|
| `listing_id` | listing_id | int64 | 0.00% | 28871 to 1704341300366137856 | 28871; 768737; 4153760 | one row per listing review date in the summary file | Not defined in official dictionary. | Official type: not specified |
| `date` | unchanged unless documented in transformation | str | 0.00% | 2010-08-16 to 2026-06-28 | 2010-08-22; 2014-10-19; 2015-02-09 | one row per listing review date in the summary file | Not defined in official dictionary. | Official type: not specified |

### `neighbourhoods`

- **Source row count inspected**: 22
- **Business grain**: one row per source neighbourhood label

| Source Column | Canonical Name | Observed Type | Null Rate | Range / Values | Sample Values | Grain | Interpretation | Notes |
|---|---|---|---:|---|---|---|---|---|
| `neighbourhood_group` | unchanged unless documented in transformation | float64 | 100.00% | n/a | n/a | one row per source neighbourhood label | The neighbourhood group as geocoded using the latitude and longitude against neighborhoods as defined by open or public digital shapefiles. | Official type: text; calculated by source |
| `neighbourhood` | unchanged unless documented in transformation | str | 0.00% | 20+ observed values | Bijlmer-Centrum; Bijlmer-Oost; Bos en Lommer | one row per source neighbourhood label | The neighbourhood as geocoded using the latitude and longitude against neighborhoods as defined by open or public digital shapefiles. | Official type: text; calculated by source |

### `neighbourhoods_geojson`

- **Source row count inspected**: 22
- **Business grain**: one feature per neighbourhood polygon or multipolygon

| Source Column | Canonical Name | Observed Type | Null Rate | Range / Values | Sample Values | Grain | Interpretation | Notes |
|---|---|---|---:|---|---|---|---|---|
| `neighbourhood` | unchanged unless documented in transformation | str | 0.00% | 20+ observed values | Bijlmer-Oost; Oud-Noord; Noord-Oost | one feature per neighbourhood polygon or multipolygon | Not defined in official dictionary; documented from observed source schema. | Official type: not specified |
| `neighbourhood_group` | unchanged unless documented in transformation | object | 100.00% | n/a | n/a | one feature per neighbourhood polygon or multipolygon | Not defined in official dictionary; documented from observed source schema. | Official type: not specified |
| `geometry_type` | unchanged unless documented in transformation | str | 0.00% | MultiPolygon (22) | MultiPolygon | one feature per neighbourhood polygon or multipolygon | Not defined in official dictionary; documented from observed source schema. | Official type: not specified |

## Coverage Gaps and Source Caveats

- Location coordinates are anonymized by Airbnb, so distance and map outputs are approximate.
- Calendar availability does not separate booked nights from host-blocked nights; downstream metrics must use `availability_rate` and `occupancy_proxy` labels carefully.
- Review fields are incomplete demand signals because guests are not required to leave reviews.
- Price exports use a dollar-sign artifact even when the local currency is different; parsing must treat the symbol as formatting, not USD evidence.
- Several quote-related columns in the detailed listings file are present in the Amsterdam snapshot but are not needed for current analysis decisions yet.
- This is a single snapshot, so no trend or current-market claim is valid without later snapshots.
