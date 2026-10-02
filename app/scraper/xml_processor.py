import re
import warnings

import pandas as pd
from bs4 import BeautifulSoup, Tag, XMLParsedAsHTMLWarning

from app.stocks.ticker_resolver import TickerResolver
from app.utils.logger import get_logger, log_safe

logger = get_logger(__name__)

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

# Strip ``<!ENTITY ...>`` and ``<!DOCTYPE ...>`` declarations before parsing.
# We currently use BeautifulSoup with lxml's HTML parser, which does not
# resolve external entities, so XXE is not exploitable today. This sanitiser
# is belt-and-suspenders: if a future change switches to ``lxml-xml`` or a
# different parser that honours DTDs, SEC filings cannot smuggle in external
# entity references that exfiltrate local files or trigger SSRF.
# We strip ENTITY first so the subsequent DOCTYPE match doesn't have to deal
# with nested ``>`` characters inside the internal subset.
_ENTITY_RE = re.compile(rb"<!ENTITY[^>]*>", re.IGNORECASE)
_DOCTYPE_RE = re.compile(rb"<!DOCTYPE[^>]*>", re.IGNORECASE)


def _sanitize_xml(content):
    """
    Remove DOCTYPE/ENTITY declarations from raw filing bytes.
    Accepts ``str`` or ``bytes`` and always returns ``bytes`` (the form
    BeautifulSoup prefers and which avoids decode round-trips).
    """
    if isinstance(content, str):
        content = content.encode("utf-8")
    content = _ENTITY_RE.sub(b"", content)
    return _DOCTYPE_RE.sub(b"", content)


def _get_tag_text(element, tag_suffix):
    """
    Safely find a tag by its suffix and return its stripped text, or None.
    """
    if not element:
        return None
    tag = element.find(lambda t: t.name.endswith(tag_suffix))
    if tag:
        value_tag = tag.find("value")
        if value_tag:
            return value_tag.text.strip()
        return tag.text.strip()
    return None


def xml_to_dataframe_13f(xml_content):
    """
    Parses the XML content of a 13F filing and returns the data as a Pandas DataFrame.
    """
    soup_xml = BeautifulSoup(_sanitize_xml(xml_content), "lxml")

    columns = ["Company", "CUSIP", "Value", "Shares", "Put/Call"]

    data = []

    for info_table in soup_xml.find_all(lambda tag: tag.name.endswith("infotable")):
        company = _get_tag_text(info_table, "nameofissuer")
        cusip = _get_tag_text(info_table, "cusip")
        value = _get_tag_text(info_table, "value")
        shares = _get_tag_text(info_table, "sshprnamt")
        put_call = _get_tag_text(info_table, "putcall") or ""

        data.append([company, cusip, value, shares, put_call])

    df = pd.DataFrame(data, columns=columns)

    df = df[df["Put/Call"] == ""].drop("Put/Call", axis=1)

    # PRN (principal-amount) rows are kept on purpose: the saved per-fund CSV
    # must stay a faithful record of the filing, debt positions included.
    # Equity-only views belong to the analysis layer on top.

    df = df[(df["Value"] != "0") & (df["Shares"] != "0")]

    df["Company"] = df["Company"].str.strip().str.replace(r"\s+", " ", regex=True)
    df["CUSIP"] = df["CUSIP"].str.upper()
    df["Value"] = pd.to_numeric(df["Value"], errors="coerce")
    df["Shares"] = pd.to_numeric(df["Shares"], errors="coerce")

    # Unparseable numbers must surface, not silently corrupt the report
    unparseable_mask = df["Value"].isna() | df["Shares"].isna()
    if unparseable_mask.any():
        logger.warning(
            "Dropped %d row(s) with unparseable Value/Shares from 13F filing",
            int(unparseable_mask.sum()),
        )
        df = df[~unparseable_mask]
    df["Shares"] = df["Shares"].astype(int)

    # Some funds report Value in thousands instead of full dollars (SEC XML
    # spec requires full dollars). Median implied price < $0.50 across an
    # institutional portfolio is only possible if scaled by 1000.
    implied_prices = (df["Value"] / df["Shares"].replace(0, pd.NA)).dropna()
    if implied_prices.empty:
        return df
    median_price = float(implied_prices.median())
    PRICE_THRESHOLD = 0.50

    if median_price < PRICE_THRESHOLD:
        df["Value"] = df["Value"] * 1000

    return df.groupby(["CUSIP"], as_index=False).agg(
        {"Company": "max", "Value": "sum", "Shares": "sum"}
    )


def xml_to_dataframe_schedule(xml_content):
    """
    Parses the XML content of a Schedule 13G/D filing and returns the data as a Pandas DataFrame.
    """
    soup_xml = BeautifulSoup(_sanitize_xml(xml_content), "lxml")

    columns = ["Company", "CUSIP", "CIK", "Shares", "Class_Pct", "Owner_CIK", "Owner", "Date"]

    data = []

    form_data = soup_xml.find("formdata")
    company = _get_tag_text(form_data, "issuername")
    cusip = _get_tag_text(form_data, "issuercusipnumber") or _get_tag_text(form_data, "issuercusip")
    cik = _get_tag_text(form_data, "issuercik")
    date = _get_tag_text(form_data, "dateofevent") or _get_tag_text(
        form_data, "eventdaterequiresfilingthisstatement"
    )

    for reporting_person in soup_xml.find_all(
        "coverpageheaderreportingpersondetails"
    ) or soup_xml.find_all("reportingpersoninfo"):
        shares = _get_tag_text(reporting_person, "aggregateamountowned") or _get_tag_text(
            reporting_person, "reportingpersonbeneficiallyownedaggregatenumberofshares"
        )
        # Percentage of the class: the only figure in the filing that ties the
        # reported share count to the size of the class it belongs to, which is
        # what reconciles a depositary receipt with its underlying shares.
        class_pct = _get_tag_text(reporting_person, "classpercent") or _get_tag_text(
            reporting_person, "percentofclass"
        )
        owner_cik = _get_tag_text(reporting_person, "rptownercik") or _get_tag_text(
            reporting_person, "reportingpersoncik"
        )
        owner_name = _get_tag_text(reporting_person, "reportingpersonname")

        data.append([company, cusip, cik, shares, class_pct, owner_cik, owner_name, date])

    df = pd.DataFrame(data, columns=columns)

    df["Company"] = df["Company"].str.replace(r"\s+", " ", regex=True)
    df["CUSIP"] = df["CUSIP"].str.upper()
    df["CIK"] = df["CIK"].str.strip()
    df["Shares"] = pd.to_numeric(df["Shares"], errors="coerce").fillna(0).astype(int)
    df["Class_Pct"] = pd.to_numeric(df["Class_Pct"], errors="coerce")
    df["Owner_CIK"] = df["Owner_CIK"].str.strip()
    df["Owner"] = df["Owner"].str.upper()
    df["Date"] = pd.to_datetime(df["Date"], format="%m/%d/%Y", errors="coerce")

    return df


_COMMON_TITLE_RE = re.compile(r"\b(?:COMMON|ORDINARY)\b")
_NON_COMMON_TITLE_RE = re.compile(r"\b(?:PREFERRED|PREFERENCE|WARRANTS?|RIGHTS?|UNITS?|NOTES?)\b")
_CLASS_DESIGNATOR_RE = re.compile(r"\b(?:CLASS|SERIES)\s+([A-Z0-9]+)\b")


def _security_class(title):
    """
    Maps a Form 4 security title to a class key: wording variants of the same
    common class (e.g. with or without the par value) share a key, while a
    distinct class designator or a non-common security keeps its own.
    """
    normalized = re.sub(r"\s+", " ", (title or "").upper()).strip()
    if _COMMON_TITLE_RE.search(normalized) and not _NON_COMMON_TITLE_RE.search(normalized):
        designator = _CLASS_DESIGNATOR_RE.search(normalized)
        return ("COMMON", designator.group(1) if designator else "")
    return ("OTHER", normalized)


def _pick_form4_class(classes: list[tuple[str, str]], ticker: str | None):
    """
    Chooses the Form 4 security class to report: the common class without a
    designator, else common Class A, else the first common class, else the first
    class listed. Warns when several distinct common designators are present.
    """
    common = [c for c in classes if c[0] == "COMMON"]
    if len(common) > 1:
        logger.warning(
            "Form 4 for %s lists several common classes (%s): choosing one",
            log_safe(ticker),
            log_safe(", ".join(c[1] or "-" for c in common)),
        )
    # On dual-class issuers the unlisted class (often B) can be listed first.
    for designator in ("", "A"):
        if ("COMMON", designator) in common:
            return ("COMMON", designator)
    return next(iter(common or classes), None)


def xml_to_dataframe_4(xml_content):
    """
    Parses the XML content of a Form 4 filing and returns the data as a Pandas DataFrame.
    It correctly extracts the final share ownership for each reporting owner.

    Positions are tracked per security class, and only one class is reported
    because different classes are different securities: the common class picked
    by ``_pick_form4_class``, or the first class listed when none looks like
    common stock. Within that class the latest post-transaction
    amount of each ownership nature (direct, and each kind of indirect) is summed.
    """
    soup_xml = BeautifulSoup(_sanitize_xml(xml_content), "lxml")

    columns = ["Company", "Ticker", "CIK", "Shares", "Owner_CIK", "Owner", "Date"]
    data = []

    issuer = soup_xml.find("issuer")
    company = _get_tag_text(issuer, "issuername")
    ticker = _get_tag_text(issuer, "issuertradingsymbol")
    cik = _get_tag_text(issuer, "issuercik")
    date = _get_tag_text(soup_xml, "periodofreport")

    owner_shares: dict[tuple[str, str], dict[tuple[str, str], float]] = {}

    def process_item(item):
        """
        Helper to extract holding info from a transaction or holding tag.
        """
        raw_shares = _get_tag_text(item, "sharesownedfollowingtransaction")
        if raw_shares is None:
            logger.warning("Form 4: skipping item without sharesownedfollowingtransaction")
            return
        try:
            shares_post = float(raw_shares.replace(",", ""))
        except ValueError:
            logger.warning(
                "Form 4: skipping item with unparseable share count %s", log_safe(raw_shares)
            )
            return
        ownership_nature = item.find("ownershipnature")
        direct_indirect = _get_tag_text(ownership_nature, "directorindirectownership")
        nature_of_ownership = _get_tag_text(ownership_nature, "natureofownership") or "Direct"

        key = (str(direct_indirect).strip().upper(), str(nature_of_ownership).strip().upper())
        security_class = _security_class(_get_tag_text(item, "securitytitle"))
        owner_shares.setdefault(security_class, {})[key] = shares_post

    non_derivative_table = soup_xml.find("nonderivativetable")
    if isinstance(non_derivative_table, Tag):
        for child in non_derivative_table.children:
            if (
                isinstance(child, Tag)
                and child.name
                and (
                    "nonderivativetransaction" in child.name or "nonderivativeholding" in child.name
                )
            ):
                process_item(child)

    chosen_class = _pick_form4_class(list(owner_shares), ticker)
    total_shares = int(sum(owner_shares[chosen_class].values())) if chosen_class else 0

    for reporting_person in soup_xml.find_all("reportingowner"):
        owner_cik = _get_tag_text(reporting_person, "rptownercik")
        owner_name = _get_tag_text(reporting_person, "rptownername")

        data.append([company, ticker, cik, total_shares, owner_cik, owner_name, date])

    df = pd.DataFrame(data, columns=columns)

    df["Company"] = df["Company"].str.replace(r"\s+", " ", regex=True)
    df["Ticker"] = df["Ticker"].str.replace(r"[^a-zA-Z0-9]", "", regex=True).str.upper()
    df["CIK"] = df["CIK"].str.strip()
    df["Shares"] = pd.to_numeric(df["Shares"], errors="coerce").fillna(0).astype(int)
    df["Owner_CIK"] = df["Owner_CIK"].str.strip()
    df["Owner"] = df["Owner"].str.upper()
    df["Date"] = pd.to_datetime(df["Date"], format="%Y-%m-%d", errors="coerce")

    return TickerResolver.assign_cusip(df)
