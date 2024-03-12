import dataclasses
import itertools
import json
import os
import pathlib
from typing import Literal

import googlemaps
from googlemaps import distance_matrix

from utils import types

_CACHE_PATH = pathlib.Path("commutes_cache.json")


def _save_cache(listings: list[types.ListingStage2]):
    _CACHE_PATH.write_text(
        json.dumps(
            {
                listing_and_commutes.listing_id: {
                    "bicycling": dataclasses.asdict(
                        listing_and_commutes.bicycling_commute
                    ),
                    "transit": dataclasses.asdict(listing_and_commutes.transit_commute),
                }
                for listing_and_commutes in listings
            }
        )
    )


def _load_cache(listings: list[types.ListingStage1]) -> list[types.ListingStage2]:
    if not _CACHE_PATH.exists():
        return []
    commute_by_mode_by_listing_id_str = json.loads(_CACHE_PATH.read_text())
    commute_by_mode_by_listing_id = {
        types.ListingID(int(listing_id_str)): commute_by_mode
        for listing_id_str, commute_by_mode in commute_by_mode_by_listing_id_str.items()
    }
    listings_with_commutes = []
    for listing in listings:
        if listing.listing_id not in commute_by_mode_by_listing_id:
            continue
        commute_by_mode = commute_by_mode_by_listing_id[listing.listing_id]
        listing_with_commutes = types.ListingStage2(
            bicycling_commute=types.Commute(**commute_by_mode["bicycling"]),
            transit_commute=types.Commute(**commute_by_mode["transit"]),
            **dataclasses.asdict(listing),
        )
        listings_with_commutes.append(listing_with_commutes)
    return listings_with_commutes


def _compute_commute_by_mode(
    latlngs: list[str],
    mode: Literal["bicycling", "transit"],
    work_address: str,
) -> list[types.Commute]:
    client = googlemaps.Client(key=os.environ["GOOGLE_MAPS_API_KEY"])
    response = distance_matrix.distance_matrix(
        client,
        [work_address],
        latlngs,
        mode=mode,
    )
    [row] = response["rows"]
    distance_dicts = row["elements"]
    assert len(distance_dicts) == len(latlngs)
    commutes = [
        types.Commute(
            distance_km=d["distance"]["value"] / 1000,
            duration_mins=d["duration"]["value"] / 60,
        )
        for d in distance_dicts
    ]
    assert len(commutes) == len(latlngs)
    return commutes


def add_commutes(
    listings: list[types.ListingStage1],
    work_address: str,
) -> list[types.ListingStage2]:
    listings_with_commutes = _load_cache(listings)
    print(f"Loaded commutes for {len(listings_with_commutes)} listings from cache")
    cached_listing_ids = {listing.listing_id for listing in listings_with_commutes}
    uncached_listings = [
        listing for listing in listings if listing.listing_id not in cached_listing_ids
    ]
    for listings_chunk in itertools.batched(uncached_listings, n=25):
        latlngs = [t.latlng for t in listings_chunk]
        bicycling_commutes = _compute_commute_by_mode(
            latlngs, "bicycling", work_address
        )
        transit_commutes = _compute_commute_by_mode(latlngs, "transit", work_address)
        for listing, bicycling, transit in zip(
            listings_chunk,
            bicycling_commutes,
            transit_commutes,
        ):
            listings_with_commutes.append(
                types.ListingStage2(
                    bicycling_commute=bicycling,
                    transit_commute=transit,
                    **dataclasses.asdict(listing),
                )
            )
    print(f"Sent {len(uncached_listings)} queries for commutes\n")
    assert len(listings_with_commutes) == len(listings)
    _save_cache(listings_with_commutes)
    return listings_with_commutes


def filter_commutes(
    listings_with_commutes: list[types.ListingStage2],
    min_commute_mins: int,
    max_commute_mins: int,
) -> list[types.ListingStage2]:
    filtered_listings = []
    for listing in listings_with_commutes:
        commutes_mins = [
            listing.bicycling_commute.duration_mins,
            listing.transit_commute.duration_mins,
        ]
        if (
            min(commutes_mins) > min_commute_mins
            and max(commutes_mins) < max_commute_mins
        ):
            filtered_listings.append(listing)
    return filtered_listings
