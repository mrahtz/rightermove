import concurrent.futures
import dataclasses
import json
import pathlib
import pprint
import sys
from typing import TypeVar

import requests
import tqdm

from utils import types

_USER_AGENT_HEADER = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 "
        "Safari/537.36"
    )
}

_RAW_DATA_CACHE_PATH = pathlib.Path("raw_data_cache.json")
_IMAGES_CACHE_PATH = pathlib.Path("images_cache/")

T = TypeVar("T")


def _fetch_results_page(
    search_params: dict[str, int | str | float],
    listing_index: int,
) -> types.ListingDict:
    response = requests.get(
        "https://www.rightmove.co.uk/api/_search",
        params={**search_params, "index": listing_index},
        headers=_USER_AGENT_HEADER,
    )
    assert response.status_code == 200, response.content
    return types.ListingDict(response.json())


def _fetch_listing_dicts(
    search_params: dict[str, int | str | float]
) -> list[types.ListingDict]:
    listing_dicts = []
    expected_num_listing_dicts = None
    listing_index = 0
    with tqdm.tqdm(unit="page") as progress_bar:
        while True:
            results_page = _fetch_results_page(search_params, listing_index)
            listing_dicts.extend(results_page["properties"])
            if listing_index == 0:
                expected_num_listing_dicts = int(
                    results_page["resultCount"].replace(",", "")
                )
                progress_bar.total = int(results_page["pagination"]["total"])
            progress_bar.update(1)
            listing_index = results_page["pagination"].get("next", None)
            if not listing_index:
                break

    if len(listing_dicts) != expected_num_listing_dicts:
        print(
            "Warning: expected {} listings, but got {}".format(
                expected_num_listing_dicts,
                len(listing_dicts),
            )
        )
    return listing_dicts


def _fetch_listing_pages(
    listing_ids: list[types.ListingID],
) -> dict[types.ListingID, str]:
    fetch_results_by_listing_id = _parallel_fetch(
        {
            listing_id: [f"https://www.rightmove.co.uk/properties/{listing_id}"]
            for listing_id in listing_ids
        }
    )
    return {
        listing_id: fetch_results_by_listing_id[listing_id][0].content.decode()
        for listing_id in listing_ids
    }


def _parallel_fetch(
    urls_by_key: dict[T, list[str]]
) -> dict[T, list[types.FetchResult]]:
    if not urls_by_key:
        return {}
    fetch_results_by_key = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as executor:
        key_by_future = {}
        for key, urls in urls_by_key.items():
            future = executor.submit(
                lambda lambda_urls=tuple(urls): [
                    types.FetchResult(
                        url=url,
                        content=requests.get(url, headers=_USER_AGENT_HEADER).content,
                    )
                    for url in lambda_urls
                ],
            )
            key_by_future[future] = key
        for future in tqdm.tqdm(
            concurrent.futures.as_completed(key_by_future),
            unit="listing",
            total=len(key_by_future),
        ):
            key = key_by_future[future]
            fetch_results_by_key[key] = future.result()
    return fetch_results_by_key


def scrape_raw_data(search_params: types.SearchParams) -> types.RawScrapeData:
    print("Search parameters:")
    pprint.pprint(search_params)

    print("Fetching listings summary...")
    listing_dicts = _fetch_listing_dicts(search_params)
    listing_ids = [types.ListingID(int(d["id"])) for d in listing_dicts]

    print("Fetching individual listings...")
    listing_html_by_listing_id = _fetch_listing_pages(listing_ids)

    return types.RawScrapeData(
        search_params=search_params,
        listing_dicts=listing_dicts,
        listing_html_by_listing_id=listing_html_by_listing_id,
    )


def save_raw_data_cache(data: types.RawScrapeData) -> None:
    _RAW_DATA_CACHE_PATH.write_text(
        json.dumps(
            {
                "search_params": data.search_params,
                "listing_dicts": data.listing_dicts,
                "listing_html_by_listing_id": data.listing_html_by_listing_id,
            }
        )
    )


def load_raw_data_cache(
    search_params_from_arguments: types.SearchParams,
) -> types.RawScrapeData:
    cache = json.loads(_RAW_DATA_CACHE_PATH.read_text())
    cache_search_params = cache["search_params"]
    if cache_search_params != search_params_from_arguments:
        print(
            f"Search parameters from cache:\n\n{cache_search_params}\n\n"
            f"do not match parameters from arguments:\n\n{search_params_from_arguments}",
            file=sys.stderr,
        )
        exit(1)
    listing_dicts = cache["listing_dicts"]
    listing_html_by_listing_id = cache["listing_html_by_listing_id"]
    listing_html_by_listing_id = {
        types.ListingID(int(l_id)): h for l_id, h in listing_html_by_listing_id.items()
    }
    return types.RawScrapeData(
        search_params=cache_search_params,
        listing_dicts=listing_dicts,
        listing_html_by_listing_id=listing_html_by_listing_id,
    )


def _load_cached_images() -> dict[types.ListingID, list[bytes]]:
    image_paths = _IMAGES_CACHE_PATH.glob("*")
    listing_ids = [types.ListingID(int(p.stem.split("_")[0])) for p in image_paths]
    listing_ids = [types.ListingID(int(l_id)) for l_id in listing_ids]
    images_by_listing_id = {}
    for listing_id in listing_ids:
        listing_image_paths = pathlib.Path("images_cache").glob(f"{listing_id}_*")
        images = [p.read_bytes() for p in listing_image_paths]
        images_by_listing_id[listing_id] = images
    return images_by_listing_id


def _save_cached_images(
    image_by_listing_id: dict[types.ListingID, list[bytes]]
) -> None:
    for listing_id, images in image_by_listing_id.items():
        for image_num, image in enumerate(images):
            path = _IMAGES_CACHE_PATH / f"{listing_id}_{image_num}.jpeg"
            path.write_bytes(image)


def add_images(
    listings: list[types.ListingStage2],
) -> list[types.ListingStage3]:
    cached_images_by_listing_id = _load_cached_images()
    print(f"Loaded images for {len(cached_images_by_listing_id)} listings from cache")

    urls_to_fetch_by_listing_id = {}
    for listing in listings:
        listing_id = listing.listing_id
        if listing_id in cached_images_by_listing_id:
            continue
        urls_to_fetch_by_listing_id[listing_id] = sorted(listing.image_urls)
    fetch_results_by_listing_id = _parallel_fetch(urls_to_fetch_by_listing_id)
    print(f"Fetched images for {len(urls_to_fetch_by_listing_id)} listings\n")
    fetched_images_by_listing_id = {
        listing_id: [fetch_result.content for fetch_result in fetch_results]
        for listing_id, fetch_results in fetch_results_by_listing_id.items()
    }
    images_by_listing_id = {
        **cached_images_by_listing_id,
        **fetched_images_by_listing_id,
    }
    _save_cached_images(images_by_listing_id)

    listings_with_images = []
    for listing in listings:
        listing_id = listing.listing_id
        images = images_by_listing_id[listing_id]
        listings_with_images.append(
            types.ListingStage3(
                listing_id=listing_id,
                listing_url=listing.listing_url,
                title=listing.title,
                image_urls=listing.image_urls,
                price_str=listing.price_str,
                added_or_reduced=listing.added_or_reduced,
                tenancy_minimum_months=listing.tenancy_minimum_months,
                latlng=listing.latlng,
                agent=listing.agent,
                bicycling_commute=listing.bicycling_commute,
                transit_commute=listing.transit_commute,
                images=images,
            )
        )

    return listings_with_images
