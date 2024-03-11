#!/usr/bin/env python

import argparse
import base64
import json
import os
import pathlib
import re

from utils import commute_utils
from utils import scraping_utils
from utils import types

parser = argparse.ArgumentParser()
parser.add_argument(
    "--rent_or_buy", choices=["short_term_rent", "long_term_rent", "buy"], required=True
)
parser.add_argument("--min_price", type=int, default=100_000)
parser.add_argument("--max_price", type=int, default=500_000)
parser.add_argument("--min_commute_mins", type=int, default=0)
parser.add_argument("--max_commute_mins", type=int, default=60)
parser.add_argument("--sort", choices=["price"], default="price")
parser.add_argument("--sort_order", choices=["asc", "desc"], default="asc")
parser.add_argument("--discard_agents", type=str, default="")
parser.add_argument("--min_tenancy_months", type=int, default=None)
parser.add_argument("--use_raw_data_cache", action=argparse.BooleanOptionalAction)
parser.add_argument("--home_address", type=str, required=True)
args = parser.parse_args()


def extract_price_str(listing_dict: types.ListingDict) -> str:
    if args.rent_or_buy == "buy":
        price = listing_dict["price"]["amount"]
        return f"£{price}"
    elif "rent" in args.rent_or_buy:
        display_prices = listing_dict["price"]["displayPrices"]
        display_prices = [d["displayPrice"] for d in display_prices]
        [display_price] = [p for p in display_prices if "pcm" in p]
        price = int(re.search(r"[\d,]+", display_price).group(0).replace(",", ""))
        return f"£{price} per month"
    else:
        raise RuntimeError()


def parse_listings(
    listing_dicts: list[types.ListingDict],
    listing_html_by_listing_id: dict[types.ListingID, str],
) -> list[types.ListingStage1]:
    minimum_months_by_listing_id = {
        listing_id: extract_minimum_months(listing_id, listing_html)
        for listing_id, listing_html in listing_html_by_listing_id.items()
    }

    listings: list[types.ListingStage1] = []
    processed_listing_ids = set()
    for listing_dict in listing_dicts:
        listing_id = types.ListingID(int(listing_dict["id"]))
        if listing_id in processed_listing_ids:
            continue
        title = listing_dict["displayAddress"]
        listing_url = f"https://www.rightmove.co.uk/properties/{listing_dict['id']}"
        location = listing_dict["location"]
        latlng = f"{location['latitude']},{location['longitude']}"
        listings.append(
            types.ListingStage1(
                listing_id=listing_id,
                image_urls=[
                    im["srcUrl"] for im in listing_dict["propertyImages"]["images"]
                ],
                title=title,
                price_str=extract_price_str(listing_dict),
                listing_url=listing_url,
                latlng=latlng,
                added_or_reduced=listing_dict["addedOrReduced"],
                tenancy_minimum_months=minimum_months_by_listing_id[listing_id],
                agent=listing_dict["customer"]["branchDisplayName"],
            )
        )
        processed_listing_ids.add(listing_id)

    return listings


def get_map_html(latlng: str, zoom: int, width_percent: int) -> str:
    return f"""<iframe
  class="map"
  width="{width_percent}%"
  height="450"
  zoom="18"
  style="border:0"
  loading="lazy"
  referrerpolicy="no-referrer-when-downgrade"
  src="https://www.google.com/maps/embed/v1/place?key={os.environ['GOOGLE_MAPS_API_KEY']}&q=({latlng}&zoom={zoom})"
>
</iframe>"""


def write_html(listings_with_commutes: list[types.ListingStage3]):
    html = """
    <!DOCTYPE html>
    <html>
    <head>
    <meta charset="UTF-8">
    <script
        src="https://code.jquery.com/jquery-3.7.1.min.js"
        integrity="sha256-/JqT3SQfawRcv/BIHPThkBvs0OEvtFFmqPF/lYI/Cxo=" crossorigin="anonymous">
    </script>
    <script type="text/javascript" src="https://livejs.com/live.js"></script>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@3.4.1/dist/css/bootstrap.min.css"
        integrity="sha384-HSMxcRTRxnN+Bdg0JdbxYKrThecOKuH5zCYotlSAcp1+c8xmyTe9GYg1l9a69psu" crossorigin="anonymous">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@3.4.1/dist/css/bootstrap-theme.min.css"
        integrity="sha384-6pzBo3FDv/PJ8r2KRkGHifhEocL+1X2rVCTTkUfGk7/0pbek5mMa1upzvWbrUbOZ" crossorigin="anonymous">
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@3.4.1/dist/js/bootstrap.min.js"
        integrity="sha384-aJ21OjlMXNL5UyIl/XNwTMqvzeRMZH2w8c5cRVpzpU8Y5bApTppSuUkhZXN0VxHd" crossorigin="anonymous">
    </script>
    <style>
    body {
        padding: 20px;
    }
    .image-container{
        margin-top: 20px;
        display: grid;
        grid-template-columns: repeat(auto-fill, 49%);
        grid-gap: 5px;
    }
    img {
        width: 100%;
        border-radius: 5px;
    }
    section {
        border-radius: 10px;
        box-shadow: 0px 0px 20px rgb(0, 0, 0, 0.2);
        padding: 20px;
        margin-bottom: 50px;
        max-width: 1100px;
        margin-left: auto;
        margin-right: auto;
        
    }
    h1 {
        margin-top: 0;
    }
    .map {
        margin-top: 10px;
        border-radius: 5px;
    }
    </style>
    </head>
    <body>
    """
    for listing_with_commute in listings_with_commutes:
        html += "<section>\n"
        html += (
            "<h1>"
            f"<a href=https://www.rightmove.co.uk/properties/{listing_with_commute.listing_id}>"
            f"Listing {listing_with_commute.listing_id}"
            "</a>"
            "</h1>"
        )
        html += f"<h3>{listing_with_commute.price_str}</h3>\n"
        html += (
            f"<h3>Cycling: {listing_with_commute.bicycling_commute.distance_km:.1f} km, "
            f"{listing_with_commute.bicycling_commute.duration_mins:.0f} min</h3>\n"
        )
        html += (
            f"<h3>Transit: {listing_with_commute.transit_commute.distance_km:.1f} km, "
            f"{listing_with_commute.transit_commute.duration_mins:.0f} min</h3>\n"
        )
        html += f"<h3>{listing_with_commute.added_or_reduced}</h3>\n"
        html += '<div class="image-container">\n'
        for image_bytes in listing_with_commute.images:
            image_base64 = base64.b64encode(image_bytes).decode()
            html += f'<img src="data:image/jpeg;base64,{image_base64}" />\n'
        html += "</div>"
        html += get_map_html(listing_with_commute.latlng, zoom=18, width_percent=49)
        html += get_map_html(listing_with_commute.latlng, zoom=12, width_percent=49)
        html += "</section>\n"
    html += """</body>
    </html>"""
    path = pathlib.Path("/tmp/output.html")
    path.write_text(html)
    path.rename("output.html")
    print("Wrote to output.html")


def extract_listing_descriptions(listing_html) -> str:
    re_match = re.search(r'"description":(.*?[^\\]"),', listing_html)
    assert re_match is not None, breakpoint()
    description_json = re_match.group(1)
    return json.loads(description_json)


def extract_minimum_months(
    listing_id: types.ListingID, listing_html: str
) -> int | None:
    # Try extracting from the actual 'Minimum Tenancy' field in the listing.

    match1 = re.search(r"Min\. tenancy: </dt><dd>(\d+) months", listing_html)
    if match1:
        return match1.group(1)

    # Otherwise, look for a mention of the minimum tenancy in the listing description.

    listing_description = extract_listing_descriptions(listing_html)

    if "Minimum 7-day stay" in listing_description:
        return 1

    patterns = (
        r"Min(?:imum)? (?:[tT]erm|tenancy|length of stay|contract)[^<]*?(\d+)(?: months|mths)",
        r"(\d+)[- ][mM]onth(?: term)? [mM]inimum",
        r"minimum (\d+)[- ]month",
    )
    for pattern in patterns:
        re_match = re.search(pattern, listing_description)
        if re_match is not None:
            return int(re_match.group(1))

    instances_of_minimum = re.findall(
        ".{10}[Mm]in[^adegostu].{50}", listing_description
    )
    instances_of_minimum = [
        s
        for s in instances_of_minimum
        if not any(
            key in s
            for key in [
                "min walk",
                "1 min",
                "5 min",
                "10 min",
                "25 min",
                "30 min",
                "min away",
                "Dominion",
                "administration",
                "mini fridge",
                "Mini fridge",
                "mini-fridge",
                "minimum of £",
                "minimum £",
            ]
        )
    ]
    if instances_of_minimum:
        print(
            f"Warning: listing ID {listing_id} may have minimum term mentioned "
            f"not captured by current parsing logic:\n{instances_of_minimum}"
        )
    return None


def main():
    # Scrape or load raw data.
    search_params = types.SearchParams(
        {
            "locationIdentifier": "REGION^87399",  # King's Cross.
            "minBedrooms": 0,
            "maxBedrooms": 0,
            "minPrice": args.min_price,
            "maxPrice": args.max_price,
            "radius": 5.0,  # Miles.
            "channel": "RENT" if "rent" in args.rent_or_buy else "BUY",
            "currencyCode": "GBP",
            "numPropertiesPerPage": 24,  # Not sure whether this matters.
            "propertyTypes": ["flat"],
            "dontShow": ["sharedOwnership"],
            "furnishType": [
                "furnished" if "rent" in args.rent_or_buy else "unfurnished"
            ],
        }
    )
    if args.rent_or_buy == "short_term_rent":
        search_params["letType"] = "shortTerm"
    elif args.rent_or_buy == "long_term_rent":
        search_params["letType"] = "longTerm"

    if args.use_raw_data_cache:
        raw_scrape_data = scraping_utils.load_raw_data_cache(search_params)
    else:
        raw_scrape_data = scraping_utils.scrape_raw_data(search_params)
        scraping_utils.save_raw_data_cache(raw_scrape_data)

    # Convert raw data to a more structured form.
    listings = parse_listings(
        raw_scrape_data.listing_dicts,
        raw_scrape_data.listing_html_by_listing_id,
    )
    print(f"Got {len(listings)} listings\n")

    # Filter listings based on minimum tenancy.
    if args.min_tenancy_months:
        listings = [
            listing
            for listing in listings
            if listing.tenancy_minimum_months
            and listing.tenancy_minimum_months <= args.min_tenancy_months
        ]
        print(f"{len(listings)} left after filtering by minimum tenancy\n")

    # Filter listings based on estate agents.
    if args.discard_agents:
        discard_agents = args.discard_agents.split(",")
        listings = [
            listing
            for listing in listings
            if not any(
                agent_substring in listing.agent.lower()
                for agent_substring in discard_agents
            )
        ]
        print(f"{len(listings)} left after filtering by agents\n")

    # Filter listings based on --min_commute_mins and --max_commute_mins.
    listings = commute_utils.add_commutes(listings, args.home_address)
    listings = commute_utils.filter_commutes(
        listings,
        min_commute_mins=args.min_commute_mins,
        max_commute_mins=args.max_commute_mins,
    )

    print(f"Found {len(listings)} listings matching requirements\n")

    # Populate images.
    listings = scraping_utils.add_images(listings)

    # Sort listings.
    if args.sort == "price":
        listings = sorted(
            listings,
            key=lambda listing: (listing.price_str, listing.listing_id),
        )
    else:
        raise RuntimeError()
    if args.sort_order == "desc":
        listings = listings[::-1]

    # Write final HTML.
    write_html(listings)


if __name__ == "__main__":
    main()
