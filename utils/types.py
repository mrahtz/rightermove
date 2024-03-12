import base64
import dataclasses
from typing import Any, NewType


ListingID = NewType("ListingID", int)
SearchParams = NewType("SearchParams", dict[str, str | int | float | list[str]])
ListingDict = NewType("ListingDict", dict[str, Any])


@dataclasses.dataclass(frozen=True)
class RawScrapeData:
    search_params: SearchParams
    listing_dicts: list[ListingDict]
    listing_html_by_listing_id: dict[ListingID, str]


@dataclasses.dataclass()
class Image:
    url: str
    image_bytes: bytes

    def to_dict(self):
        return {
            "url": self.url,
            "image_bytes": base64.b64encode(self.image_bytes).decode(),
        }

    @classmethod
    def from_dict(cls, image_dict: dict[str, str]) -> "Image":
        return Image(
            image_bytes=base64.b64decode(image_dict["image_bytes"]),
            url=image_dict["url"],
        )


@dataclasses.dataclass(frozen=True)
class FetchResult:
    url: str
    content: bytes


@dataclasses.dataclass(frozen=True)
class Commute:
    distance_km: float
    duration_mins: int


@dataclasses.dataclass(frozen=True)
class ListingStage1:
    listing_id: ListingID
    listing_url: str
    title: str
    image_urls: list[str]
    price_str: str
    added_or_reduced: str  # E.g. "Added today", "Added on 07/03/2024", "Reduced today", "Reduced on 29/02/2024".
    tenancy_minimum_months: int | None  # None = 'not specified'
    latlng: str
    agent: str


@dataclasses.dataclass(frozen=True)
class ListingStage2:
    # Fields from Listing.
    listing_id: ListingID
    listing_url: str
    title: str
    image_urls: list[str]
    price_str: str
    added_or_reduced: str
    tenancy_minimum_months: int | None  # None = 'not specified'
    latlng: str
    agent: str

    bicycling_commute: Commute
    transit_commute: Commute


@dataclasses.dataclass(frozen=True)
class ListingStage3:
    # Fields from ListingStage1.
    listing_id: ListingID
    listing_url: str
    title: str
    image_urls: list[str]
    price_str: str
    added_or_reduced: str
    tenancy_minimum_months: int | None  # None = 'not specified'
    latlng: str
    agent: str

    # Fields from ListingStage2.
    bicycling_commute: Commute
    transit_commute: Commute

    images: list[bytes]
