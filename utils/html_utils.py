import base64
import os
import pathlib

from utils import types


def _get_map_html(latlng: str, zoom: int, width_percent: int) -> str:
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
        html += _get_map_html(listing_with_commute.latlng, zoom=18, width_percent=49)
        html += _get_map_html(listing_with_commute.latlng, zoom=12, width_percent=49)
        html += "</section>\n"
    html += """</body>
    </html>"""
    path = pathlib.Path("/tmp/output.html")
    path.write_text(html)
    path.rename("output.html")
    print("Wrote to output.html")
