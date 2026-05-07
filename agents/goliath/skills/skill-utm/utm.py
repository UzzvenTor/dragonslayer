"""skill-utm — генерация UTM-метки по схеме v0.2."""
from __future__ import annotations

import argparse
import json
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

VALID_PRODUCTS = {"sysai", "openclaw", "n8n", "law"}
VALID_PREFIXES = ("H", "Hexp", "Hret", "Hscale")


def make_utm(*, campaign_id: int, ad_id: int | None,
             hypothesis: str, product: str, variation: str) -> dict:
    if product not in VALID_PRODUCTS:
        raise ValueError(f"product must be in {VALID_PRODUCTS}")
    if not any(hypothesis.startswith(p) for p in VALID_PREFIXES):
        raise ValueError(f"hypothesis must start with one of {VALID_PREFIXES}, got '{hypothesis}'")
    if not re.match(r"^[A-Za-z0-9_-]+$", variation):
        raise ValueError("variation: alphanumeric/underscore/dash only")

    return {
        "utm_source": "yandex",
        "utm_medium": "goliath",
        "utm_campaign": str(campaign_id),
        "utm_content": str(ad_id) if ad_id else "",
        "utm_term": f"{hypothesis}__{product}__{variation}",
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--campaign-id", type=int, required=True)
    ap.add_argument("--ad-id", type=int, default=None)
    ap.add_argument("--hypothesis", required=True, help="e.g. H08, Hexp02, Hscale01")
    ap.add_argument("--product", required=True, choices=sorted(VALID_PRODUCTS))
    ap.add_argument("--variation", required=True, help="e.g. v1, v2, control")
    args = ap.parse_args()

    out = make_utm(campaign_id=args.campaign_id, ad_id=args.ad_id,
                   hypothesis=args.hypothesis, product=args.product,
                   variation=args.variation)
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
