import json
import logging
import os
import time
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Optional

import requests
from bs4 import BeautifulSoup, NavigableString, ResultSet, Tag

# Configuration (could be moved to a separate config.py file)
BASE_URL: str = (
    "https://www.olx.pl/elektronika/komputery/podzespoly-i-czesci/karty-graficzne/"
)
PAGE_LIMIT: int = 3
DELAY: float = 0.1

logging.basicConfig(level=logging.INFO)
logger: logging.Logger = logging.getLogger(__name__)


class State(StrEnum):
    USED = "Używane"
    NEW = "Nowe"
    DAMAGED = "Uszkodzone"


@dataclass
class Advert:
    model: str
    price: int
    state: State


class OLXScraper:
    def __init__(self, base_url: str, page_limit: int, delay: float) -> None:
        self.base_url: str = base_url
        self.page_limit: int = page_limit
        self.delay: float = delay
        self.session: requests.Session = requests.Session()
        self.gpu_models: list[str] = [
            # NVIDIA GPUs
            "GTX 1050",
            "GTX 1050 Ti",
            "GTX 1060",
            "GTX 1070",
            "GTX 1070 Ti",
            "GTX 1080",
            "GTX 1080 Ti",
            "GTX 1650",
            "GTX 1650 Super",
            "GTX 1660",
            "GTX 1660 Ti",
            "GTX 1660 Super",
            "RTX 2060",
            "RTX 2060 Super",
            "RTX 2070",
            "RTX 2070 Super",
            "RTX 2080",
            "RTX 2080 Super",
            "RTX 2080 Ti",
            "RTX 3060",
            "RTX 3060 Ti",
            "RTX 3070",
            "RTX 3070 Ti",
            "RTX 3080",
            "RTX 3080 Ti",
            "RTX 3090",
            "RTX 3090 Ti",
            "RTX 4060",
            "RTX 4060 Ti",
            "RTX 4070",
            "RTX 4070 Ti",
            "RTX 4080",
            "RTX 4090"
            # AMD GPUs
            "RX 460",
            "RX 470",
            "RX 480",
            "RX 550",
            "RX 5500",
            "RX 5500 XT",
            "RX 560",
            "RX 5600",
            "RX 5600 XT",
            "RX 570",
            "RX 5700",
            "RX 5700 XT",
            "RX 580",
            "RX 590",
            "RX 6500",
            "RX 6500 XT",
            "RX 6600",
            "RX 6600 XT",
            "RX 6650 XT",
            "RX 6700",
            "RX 6700 XT",
            "RX 6750 XT",
            "RX 6800",
            "RX 6800 XT",
            "RX 6900 XT",
            "RX 6950 XT",
            "RX 7600",
            "RX 7700 XT",
            "RX 7800 XT",
            "RX 7900 XT",
            "RX 7900 XTX",
            # Intel GPUs
            "A380",
            "A580",
            "A750",
            "A770",
        ]

    def fetch_page(self, url: str) -> str:
        time.sleep(self.delay)
        response: requests.Response = self.session.get(url)
        response.raise_for_status()
        return response.text

    def parse_advert(self, url: str) -> Advert:
        html: str = self.fetch_page(url)
        soup: BeautifulSoup = BeautifulSoup(html, "html.parser")
        price_div: ResultSet = soup.find_all(
            "div", {"data-testid": "ad-price-container"}
        )
        price: Optional[int] = (
            int(price_div[0].find("h3").text.split(" zł")[0].replace(" ", ""))
            if price_div
            else None
        )
        model_div: ResultSet = soup.find_all("div", {"data-cy": "ad_title"})
        try:
            model: str = self.find_gpu_model(model_div[0].find("h4").text)
        except (ValueError, IndexError):
            model = "Unknown"
        state_div: Tag | NavigableString | None = soup.find("ul", class_="css-rn93um")
        state: Optional[State] = None
        if state_div and isinstance(state_div, Tag):
            state_li = next(
                (li for li in state_div.find_all("li") if "Stan:" in li.text), None
            )
            if state_li:
                state_text = state_li.text.split("Stan: ")[1].strip()
                state = State(state_text)
        if model and price and state:
            return Advert(model, price, state)
        else:
            raise ValueError("Unable to create Advert instance: missing required data")

    def get_next_page(self, soup: BeautifulSoup) -> Optional[str]:
        pagination_list: Tag | NavigableString | None = soup.find(
            "ul", class_="pagination-list"
        )
        next_page: Tag | NavigableString | None = None
        if pagination_list and isinstance(pagination_list, Tag):
            next_page = pagination_list.find("a", {"data-testid": "pagination-forward"})
            if next_page and isinstance(next_page, Tag) and next_page.has_attr("href"):
                next_page_url: str = "https://www.olx.pl" + str(next_page["href"])
                return next_page_url
        return None

    def get_offers(self, soup: BeautifulSoup) -> list[Advert]:
        offers_div: Tag | NavigableString | None = soup.find(
            "div", class_="listing-grid-container css-d4ctjd"
        )
        adverts: list[Advert] = []
        if offers_div and isinstance(offers_div, Tag):
            offers: ResultSet = offers_div.find_all("div", class_="css-u2ayx9")
            for offer in offers:
                offer_link: Tag | NavigableString | None = offer.find("a")
                if (
                    offer_link
                    and isinstance(offer_link, Tag)
                    and offer_link.has_attr("href")
                ):
                    offer_url: str = "https://www.olx.pl" + str(offer_link["href"])
                    try:
                        adverts.append(self.parse_advert(offer_url))
                    except ValueError:
                        continue
        return adverts

    def find_gpu_model(self, text: str) -> str:
        text_lower = text.lower().replace(" ", "")

        matches = [
            model
            for model in self.gpu_models
            if model.lower().strip().replace(" ", "") in text_lower
        ]

        # Check the number of matches
        if len(matches) == 1:
            return matches[0]  # One match found
        elif len(matches) == 0:
            raise ValueError("No matches found")
        else:
            raise ValueError(
                f"Multiple matches found: {matches}"
            )  # More than one match

    def scrape(self) -> list[Advert]:
        all_offers: list[Advert] = []
        current_url: Optional[str] = self.base_url
        pages_parsed: int = 0

        while current_url and pages_parsed < self.page_limit:
            html: str = self.fetch_page(current_url)
            soup: BeautifulSoup = BeautifulSoup(html, "html.parser")

            offers: list[Advert] = self.get_offers(soup)
            all_offers.extend(offers)

            current_url = self.get_next_page(soup)
            pages_parsed += 1
            logger.info(f"Parsed page {pages_parsed}: {current_url}")

        logger.info(f"Total pages parsed: {pages_parsed}")
        return all_offers


class AdvertExporter:
    @staticmethod
    def export_to_txt(
        adverts: list[Advert], filename: str = "adverts_export.txt"
    ) -> None:
        base_name, extension = os.path.splitext(filename)
        counter = 1
        while os.path.exists(filename):
            filename = f"{base_name}_{counter}{extension}"
            counter += 1

        with open(filename, "w", encoding="utf-8") as f:
            for advert in adverts:
                advert_dict: dict[str, Any] = advert.__dict__
                advert_dict["state"] = advert_dict["state"].value
                f.write(json.dumps(advert_dict, ensure_ascii=False) + "\n")


def main() -> None:
    scraper: OLXScraper = OLXScraper(BASE_URL, PAGE_LIMIT, DELAY)
    offers: list[Advert] = scraper.scrape()

    logger.info(f"Total offers scraped: {len(offers)}")
    AdvertExporter.export_to_txt(offers)
    logger.info(f"Exported {len(offers)} adverts to adverts_export.txt")


if __name__ == "__main__":
    main()
