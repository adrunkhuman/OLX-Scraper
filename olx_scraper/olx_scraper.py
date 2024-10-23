import json
import logging
import os
import time
from dataclasses import dataclass
from enum import StrEnum
from typing import Optional

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
    USED = "used"
    NEW = "new"
    DAMAGED = "broken"
    ERROR = "error"


@dataclass
class Advert:
    model: str
    price: int
    state: State
    raw_title: str


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

    def fetch_page(self, url: str, retries: int = 3) -> str:
        for _ in range(retries):
            try:
                time.sleep(self.delay)
                response: requests.Response = self.session.get(url)
                response.raise_for_status()
                return response.text
            except requests.RequestException as e:
                logger.error(f"Failed to fetch page {url}: {e}, retrying...")
        raise Exception(f"Failed to fetch page {url} after {retries} retries")

    def parse_advert(self, html: Tag) -> Optional[Advert]:
        title_element = html.find("h6")
        title = title_element.text if title_element else ""
        price_element = html.find("p", class_="css-13afqrm")
        price_text = price_element.text if price_element else ""
        if "Zamienię" in price_text:
            return None
        else:
            price = (
                (
                    price_text.replace("zł", "")
                    .replace(" ", "")
                    .replace("donegocjacji", "")
                    .split(",")[0]
                )
                if price_text
                else ""
            )
        state_element = html.find("span", class_="css-up4xui")
        state = State.ERROR
        match state_element.text if state_element else None:
            case "Używane":
                state = State.USED
            case "Nowe":
                state = State.NEW
            case "Uszkodzone":
                state = State.DAMAGED
        try:
            model = Advert(self.find_gpu_model(title), int(price), State(state), title)
        except ValueError as e:
            logger.error(f"Error parsing advert: {e}")
            model = Advert("", int(price), State.ERROR, title)
        return model

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
        offers_div: Tag | NavigableString | None = soup.find("div", class_="css-j0t2x2")
        adverts: list[Advert] = []
        if offers_div and isinstance(offers_div, Tag):
            offers: ResultSet[Tag] = offers_div.find_all("div", class_="css-1apmciz")
            for offer in offers:
                parsed_offer: Optional[Advert] = self.parse_advert(offer)
                if parsed_offer:
                    adverts.append(parsed_offer)

        return adverts

    def find_gpu_model(self, text: str) -> str:
        text_lower = text.lower().replace(" ", "")
        matches = []
        for model in self.gpu_models:
            model_lower = model.lower().strip().replace(" ", "")
            if model_lower in text_lower:
                matches.append(model)
        # Check the number of matches
        if len(matches) in [1, 3]:
            return max(matches, key=len)
        elif len(matches) == 0:
            raise ValueError(f"No matches found for {text}")
        else:
            raise ValueError(f"Multiple matches found: {matches} for {text}")

    def scrape(self) -> list[Advert]:
        all_offers: list[Advert] = []
        try:
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
        finally:
            self.session.close()

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
                f.write(json.dumps(advert.__dict__, ensure_ascii=False) + "\n")


def main() -> None:
    scraper: OLXScraper = OLXScraper(BASE_URL, PAGE_LIMIT, DELAY)
    offers: list[Advert] = scraper.scrape()

    logger.info(f"Total offers scraped: {len(offers)}")
    AdvertExporter.export_to_txt(offers)
    logger.info(f"Exported {len(offers)} adverts to adverts_export.txt")


if __name__ == "__main__":
    main()
