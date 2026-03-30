import base64
import html as html_lib
import os
import re
from typing import Dict, List, Optional

import requests
from bs4 import BeautifulSoup
from odoo import Command


BASE_URL = "https://www.tankweld.com"
PRODUCTS_PARENT_PAGE_ID = 829
USER_AGENT = "Mozilla/5.0 (compatible; TankweldCatalogImport/1.0)"
HEADERS = {"User-Agent": USER_AGENT}
REQUEST_TIMEOUT = 60
DRY_RUN = os.environ.get("TANKWELD_IMPORT_DRY_RUN", "").lower() in {"1", "true", "yes"}

TITLE_FIXES = {
    "Astm": "ASTM",
    "Cpvc": "CPVC",
    "Erw": "ERW",
    "Hdpe": "HDPE",
    "Js": "JS",
    "Mm": "MM",
    "Pvc": "PVC",
    "Rhs": "RHS",
    "Ss": "SS",
}
NOISE_IMAGE_TOKENS = (
    "logo",
    "manufacturedby",
    "wslogan",
    "kisspng-logo",
    "butch-logo",
)
ITEM_NOISE_PREFIXES = (
    "available on request",
    "cutting and bending",
    "mill certificates",
    "manufactured by",
    "special sizes and colors available",
    "special sizes and colours available",
    "standard",
    "standards",
    "thickness range",
)


def log(message: str) -> None:
    print(f"[tankweld-import] {message}")


def normalize_text(value: Optional[str]) -> str:
    text = html_lib.unescape(value or "")
    text = text.replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip(" \n\t\r-•")


def dedupe(items: List[str]) -> List[str]:
    seen = set()
    output = []
    for item in items:
        normalized = normalize_text(item)
        key = normalized.lower()
        if not normalized or key in seen:
            continue
        seen.add(key)
        output.append(normalized)
    return output


def prettify_title(value: str) -> str:
    value = normalize_text(value)
    if any(char.islower() for char in value):
        return value
    title = value.title()
    for source, target in TITLE_FIXES.items():
        title = re.sub(rf"\b{re.escape(source)}\b", target, title)
    return title


def clean_group_label(label: str) -> str:
    label = normalize_text(label)
    label = re.sub(r"^available\s+", "", label, flags=re.I)
    label = label.replace("Gauges", "Gauge")
    label = label.replace("Lengths", "Length")
    label = label.replace("Heights", "Height")
    label = label.replace("Widths", "Width")
    label = label.replace("Profiles", "Profile")
    label = label.replace("Colours", "Colour")
    label = label.replace("Colors", "Color")
    label = label.replace("Sizes", "Size")
    return label.strip(" :")


def is_noise_item(value: str) -> bool:
    text = normalize_text(value)
    if not text:
        return True
    lower = text.lower()
    if lower.endswith(":"):
        return True
    return any(lower.startswith(prefix) for prefix in ITEM_NOISE_PREFIXES)


def fetch_json(session: requests.Session, path: str, **params):
    response = session.get(
        f"{BASE_URL}{path}",
        params=params,
        headers=HEADERS,
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    return response.json()


def fetch_html(session: requests.Session, url: str) -> BeautifulSoup:
    response = session.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    return BeautifulSoup(response.text, "html.parser")


def extract_sections(pane) -> List[Dict[str, List[str]]]:
    sections = []
    current = {"heading": None, "paragraphs": [], "items": []}
    for node in pane.find_all(["h2", "h3", "h4", "h5", "p", "li"]):
        text = normalize_text(node.get_text(" ", strip=True))
        if not text:
            continue
        if node.name in {"h2", "h3", "h4", "h5"}:
            if current["heading"] or current["paragraphs"] or current["items"]:
                current["paragraphs"] = dedupe(current["paragraphs"])
                current["items"] = dedupe(current["items"])
                sections.append(current)
            current = {"heading": text, "paragraphs": [], "items": []}
            continue
        if node.name == "p":
            current["paragraphs"].append(text)
        elif node.name == "li":
            current["items"].append(text)
    if current["heading"] or current["paragraphs"] or current["items"]:
        current["paragraphs"] = dedupe(current["paragraphs"])
        current["items"] = dedupe(current["items"])
        sections.append(current)
    return sections


def choose_product_name(tab_title: str, sections: List[Dict[str, List[str]]]) -> str:
    headings = dedupe([section["heading"] for section in sections if section["heading"]])
    if len(headings) == 1:
        return headings[0]
    if headings and normalize_text(headings[0]).lower() == normalize_text(tab_title).lower():
        return headings[0]
    return prettify_title(tab_title)


def split_available_variants(text: str) -> List[str]:
    lower = text.lower()
    if "available in" not in lower:
        return []
    tail = text[lower.index("available in") + len("available in") :].strip(" :")
    if not tail or "request" in tail.lower():
        return []
    return [
        normalize_text(chunk)
        for chunk in re.split(r"\s*&\s*|\s*,\s*", tail)
        if normalize_text(chunk)
    ]


def has_following_simple_item(items: List[str], start_index: int) -> bool:
    for item in items[start_index + 1 :]:
        text = normalize_text(item)
        if not text:
            continue
        if ":" in text:
            return False
        if not is_noise_item(text):
            return True
    return False


def build_option_label(
    product_name: str,
    section_heading: Optional[str],
    group_label: Optional[str],
    item_value: str,
    multi_group_sections: bool,
) -> str:
    label = normalize_text(item_value)
    if group_label:
        label = f"{clean_group_label(group_label)}: {label}"
    heading = normalize_text(section_heading)
    if (
        multi_group_sections
        and heading
        and heading.lower() != normalize_text(product_name).lower()
    ):
        label = f"{heading} / {label}"
    return normalize_text(label)


def extract_variant_values(
    product_name: str,
    sections: List[Dict[str, List[str]]],
) -> List[str]:
    values = []
    sections_with_items = [
        section for section in sections if any(normalize_text(item) for item in section["items"])
    ]
    multi_group_sections = len(sections_with_items) > 1

    for section in sections:
        group_label = None
        section_values = []
        items = [normalize_text(item) for item in section["items"] if normalize_text(item)]

        for index, item in enumerate(items):
            lower = item.lower()
            if any(lower.startswith(prefix) for prefix in ITEM_NOISE_PREFIXES):
                continue

            if ":" in item:
                label, tail = item.split(":", 1)
                label = clean_group_label(label)
                tail = normalize_text(tail)
                if not label:
                    continue
                if has_following_simple_item(items, index):
                    group_label = label
                    continue
                if tail and "request" not in tail.lower():
                    section_values.append(
                        build_option_label(
                            product_name,
                            section["heading"],
                            label,
                            tail,
                            multi_group_sections,
                        )
                    )
                    group_label = None
                    continue
                group_label = label
                continue

            if is_noise_item(item):
                continue
            section_values.append(
                build_option_label(
                    product_name,
                    section["heading"],
                    group_label,
                    item,
                    multi_group_sections,
                )
            )

        if not section_values:
            for paragraph in section["paragraphs"]:
                paragraph_values = split_available_variants(paragraph)
                if not paragraph_values:
                    continue
                for paragraph_value in paragraph_values:
                    section_values.append(
                        build_option_label(
                            product_name,
                            section["heading"],
                            None,
                            paragraph_value,
                            multi_group_sections,
                        )
                    )

        values.extend(section_values)

    return dedupe(values)


def build_description_html(
    product_name: str,
    sections: List[Dict[str, List[str]]],
    source_url: str,
) -> str:
    parts = []
    visible_sections = [section for section in sections if section["paragraphs"] or section["items"]]
    multi_section = len(visible_sections) > 1

    for section in visible_sections:
        heading = normalize_text(section["heading"])
        if multi_section and heading and heading.lower() != normalize_text(product_name).lower():
            parts.append(f"<h4>{html_lib.escape(heading)}</h4>")
        for paragraph in section["paragraphs"]:
            parts.append(f"<p>{html_lib.escape(paragraph)}</p>")
        if section["items"]:
            parts.append("<ul>")
            for item in section["items"]:
                parts.append(f"<li>{html_lib.escape(item)}</li>")
            parts.append("</ul>")

    parts.append(
        "<p><em>Source catalog: "
        f"<a href=\"{html_lib.escape(source_url)}\" target=\"_blank\" rel=\"noopener\">"
        "Tank-Weld Metals"
        "</a></em></p>"
    )
    return "\n".join(parts)


def extract_image_urls(pane) -> List[str]:
    urls = []
    for anchor in pane.select("a[href]"):
        href = anchor.get("href")
        if href and "/wp-content/uploads/" in href:
            urls.append(href)
    for image in pane.select("img[src]"):
        src = image.get("src")
        if src and "/wp-content/uploads/" in src:
            urls.append(src)
    return dedupe(urls)


def choose_primary_image(image_urls: List[str]) -> Optional[str]:
    non_noise = [
        url
        for url in image_urls
        if not any(token in url.lower() for token in NOISE_IMAGE_TOKENS)
    ]
    return (non_noise or image_urls or [None])[0]


def parse_catalog(session: requests.Session) -> List[Dict[str, object]]:
    pages = fetch_json(
        session,
        "/wp-json/wp/v2/pages",
        parent=PRODUCTS_PARENT_PAGE_ID,
        per_page=100,
        _fields="id,slug,link,title,parent,featured_media,menu_order",
    )
    pages = sorted(
        pages,
        key=lambda page: (page.get("menu_order", 0), normalize_text(page["title"]["rendered"])),
    )

    catalog = []
    for page in pages:
        category_name = normalize_text(page["title"]["rendered"])
        soup = fetch_html(session, page["link"])
        tabs = soup.select("a.vr-tabs-nav-link")
        panes_by_id = {pane.get("id"): pane for pane in soup.select(".tab-pane[id]")}

        if not tabs:
            log(f"Skipping legacy category page without product tabs: {category_name} ({page['link']})")
            continue

        products = []
        for index, tab in enumerate(tabs, start=1):
            pane = panes_by_id.get((tab.get("href") or "").lstrip("#"))
            if pane is None:
                continue
            sections = extract_sections(pane)
            name = choose_product_name(tab.get_text(" ", strip=True), sections)
            image_urls = extract_image_urls(pane)
            primary_image_url = choose_primary_image(image_urls)
            if not primary_image_url:
                raise RuntimeError(f"Missing usable image for {category_name} / {name}")
            products.append(
                {
                    "sequence": index,
                    "name": name,
                    "option_values": extract_variant_values(name, sections),
                    "description_html": build_description_html(name, sections, page["link"]),
                    "primary_image_url": primary_image_url,
                    "extra_image_urls": [url for url in image_urls if url != primary_image_url],
                }
            )

        catalog.append(
            {
                "category_name": category_name,
                "category_slug": page["slug"],
                "category_url": page["link"],
                "sequence": page.get("menu_order", 0),
                "products": products,
            }
        )

    return catalog


def ensure_product_category(name: str, parent=False):
    ProductCategory = env["product.category"].with_context(active_test=False)
    category = ProductCategory.search(
        [("name", "=", name), ("parent_id", "=", parent.id if parent else False)],
        limit=1,
    )
    if not category:
        category = ProductCategory.create({"name": name, "parent_id": parent.id if parent else False})
    elif not category.active:
        category.active = True
    return category


def ensure_public_category(name: str, sequence: int = 0):
    PublicCategory = env["product.public.category"].with_context(active_test=False)
    category = PublicCategory.search([("name", "=", name), ("parent_id", "=", False)], limit=1)
    values = {"name": name, "sequence": sequence}
    if not category:
        category = PublicCategory.create(values)
    else:
        category.write(values)
        if not category.active:
            category.active = True
    return category


def ensure_attribute(name: str):
    Attribute = env["product.attribute"]
    attribute = Attribute.search([("name", "=", name)], limit=1)
    values = {"name": name, "create_variant": "always", "display_type": "select"}
    if not attribute:
        attribute = Attribute.create(values)
    else:
        attribute.write(values)
    return attribute


def ensure_attribute_values(attribute, names: List[str]):
    Value = env["product.attribute.value"]
    values = Value
    for index, name in enumerate(names, start=1):
        value = Value.search(
            [("attribute_id", "=", attribute.id), ("name", "=", name)],
            limit=1,
        )
        if not value:
            value = Value.create({"attribute_id": attribute.id, "name": name, "sequence": index})
        values |= value
    return values


def download_image_b64(session: requests.Session, url: str, cache: Dict[str, bytes]) -> bytes:
    if url in cache:
        return cache[url]
    response = session.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    cache[url] = base64.b64encode(response.content)
    return cache[url]


def upsert_product(
    session: requests.Session,
    image_cache: Dict[str, bytes],
    attribute,
    internal_category,
    public_category,
    product_data: Dict[str, object],
    sequence_base: int,
):
    ProductTemplate = env["product.template"].with_context(active_test=False)
    ProductImage = env["product.image"]

    template = ProductTemplate.search(
        [("name", "=", product_data["name"]), ("categ_id", "=", internal_category.id)],
        limit=1,
    )

    primary_image = download_image_b64(session, product_data["primary_image_url"], image_cache)
    values = {
        "active": True,
        "categ_id": internal_category.id,
        "default_code": False,
        "description_ecommerce": product_data["description_html"],
        "detailed_type": "product",
        "image_1920": primary_image,
        "list_price": 0.0,
        "name": product_data["name"],
        "public_categ_ids": [Command.set([public_category.id])],
        "purchase_ok": True,
        "sale_ok": True,
        "website_description": product_data["description_html"],
        "website_published": True,
        "website_sequence": sequence_base + product_data["sequence"],
    }

    if not template:
        template = ProductTemplate.create(values)
    else:
        template.write(values)

    option_values = ensure_attribute_values(attribute, product_data["option_values"])
    attribute_line = template.attribute_line_ids.filtered(lambda line: line.attribute_id == attribute)
    if len(product_data["option_values"]) > 1:
        line_values = {"attribute_id": attribute.id, "value_ids": [Command.set(option_values.ids)]}
        if attribute_line:
            attribute_line.write(line_values)
        else:
            template.write({"attribute_line_ids": [Command.create(line_values)]})
    elif attribute_line:
        attribute_line.unlink()

    ProductImage.search([("product_tmpl_id", "=", template.id)]).unlink()
    extra_images = []
    for image_url in product_data["extra_image_urls"]:
        if any(token in image_url.lower() for token in NOISE_IMAGE_TOKENS):
            continue
        extra_images.append(image_url)
    for index, image_url in enumerate(dedupe(extra_images), start=1):
        ProductImage.create(
            {
                "name": f"{template.name} Image {index}",
                "product_tmpl_id": template.id,
                "sequence": index,
                "image_1920": download_image_b64(session, image_url, image_cache),
            }
        )

    return template


def main():
    session = requests.Session()
    session.headers.update(HEADERS)
    catalog = parse_catalog(session)

    total_templates = sum(len(category["products"]) for category in catalog)
    total_option_values = sum(
        len(product["option_values"])
        for category in catalog
        for product in category["products"]
    )
    log(
        f"Prepared {total_templates} products across {len(catalog)} categories "
        f"with {total_option_values} option values"
    )

    if DRY_RUN:
        for category in catalog:
            log(f"{category['category_name']}: {len(category['products'])} products")
        return

    root_internal_category = ensure_product_category("Tankweld Imported")
    option_attribute = ensure_attribute("Tankweld Specification")
    image_cache = {}

    imported_templates = env["product.template"]
    for category_index, category in enumerate(catalog, start=1):
        public_category = ensure_public_category(category["category_name"], sequence=category_index)
        internal_category = ensure_product_category(category["category_name"], parent=root_internal_category)
        for product in category["products"]:
            template = upsert_product(
                session=session,
                image_cache=image_cache,
                attribute=option_attribute,
                internal_category=internal_category,
                public_category=public_category,
                product_data=product,
                sequence_base=category_index * 1000,
            )
            imported_templates |= template
        env.cr.commit()
        log(f"Imported category {category['category_name']} ({len(category['products'])} products)")

    imported_templates = imported_templates.with_context(active_test=False)
    variant_count = sum(len(template.product_variant_ids) for template in imported_templates)
    image_count = env["product.image"].search_count([("product_tmpl_id", "in", imported_templates.ids)])
    log(
        f"Done. Imported {len(imported_templates)} templates, "
        f"{variant_count} variants, {image_count} extra gallery images"
    )


if __name__ == "__main__":
    if "env" not in globals():
        raise RuntimeError("Run this script through `odoo shell` so `env` is available.")
    main()
