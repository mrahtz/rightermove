# Rightermove

Needs `tqdm`, `requests` and `googlemaps`.

Example usage:

```shell
$ GOOGLE_MAPS_API_KEY=YOUR_API_KEY_HERE ./main.py \
    --rent_or_buy=short_term_rent \
    --min_price=1000 \
    --max_price=3000 \
    --min_tenancy_months=6 \
    --use_raw_data_cache \
    --home_address="10 Downing Street" \
```

Spits out a static HTML page `output.html`.
