import unittest

from app.stocks.utils.identifiers import cusip_to_isin, normalize_company_name, normalize_ticker


class TestCusipToIsin(unittest.TestCase):
    """
    Verifies the CUSIP → US ISIN conversion (prepend "US", append ISO 6166 Luhn mod-10 check digit).

    Reference vectors taken from public filings / SEC EDGAR.
    """

    def test_known_isins(self):
        cases = [
            ("037833100", "US0378331005"),  # Apple Inc
            ("594918104", "US5949181045"),  # Microsoft Corp
            ("88160R101", "US88160R1014"),  # Tesla Inc
            ("478160104", "US4781601046"),  # Johnson & Johnson
            ("02079K305", "US02079K3059"),  # Alphabet Class A
            ("02079K107", "US02079K1079"),  # Alphabet Class C
            ("023135106", "US0231351067"),  # Amazon.com Inc
        ]
        for cusip, expected in cases:
            with self.subTest(cusip=cusip):
                self.assertEqual(cusip_to_isin(cusip), expected)

    def test_lowercase_cusip_is_normalised(self):
        """
        Accepts lowercase letters in the CUSIP and uppercases internally.
        """
        self.assertEqual(cusip_to_isin("88160r101"), "US88160R1014")

    def test_strips_whitespace(self):
        """
        Trims leading/trailing whitespace.
        """
        self.assertEqual(cusip_to_isin("  037833100 "), "US0378331005")

    def test_rejects_wrong_length(self):
        """
        Rejects CUSIPs that are not exactly 9 characters.
        """
        for bad in ["", "1234", "0378331000", "03783310"]:
            with self.subTest(value=bad), self.assertRaises(ValueError):
                cusip_to_isin(bad)

    def test_rejects_non_alphanumeric(self):
        """
        Rejects CUSIPs containing non-alphanumeric characters.
        """
        with self.assertRaises(ValueError):
            cusip_to_isin("037833 10")
        with self.assertRaises(ValueError):
            cusip_to_isin("037-33100")


class TestNormalizeTicker(unittest.TestCase):
    """
    Verifies that bond/derivative-style ticker strings returned by providers
    (OpenFIGI, TradingView) collapse back to the underlying equity ticker.
    """

    def test_bond_descriptor_collapses_to_issuer_prefix(self):
        """
        OpenFIGI returns bond tickers like "INFN 2.5 03/01/27"; we want "INFN".
        """
        self.assertEqual(normalize_ticker("INFN 2.5 03/01/27"), "INFN")
        self.assertEqual(normalize_ticker("INFN 3.75 08/01/28"), "INFN")

    def test_trailing_digit_descriptor_collapses_to_issuer_prefix(self):
        """
        TradingView returns bond identifiers like "INFN5636215"; we want "INFN".
        """
        self.assertEqual(normalize_ticker("INFN5636215"), "INFN")
        self.assertEqual(normalize_ticker("INFN5153317"), "INFN")

    def test_plain_equity_tickers_are_preserved(self):
        """
        Common-stock tickers pass through untouched.
        """
        for ticker in ["AAPL", "MSFT", "TSLA", "JNJ", "QQQ", "GOOGL"]:
            with self.subTest(ticker=ticker):
                self.assertEqual(normalize_ticker(ticker), ticker)

    def test_share_class_with_dot_or_dash_is_preserved(self):
        """
        Tickers using dot or dash for share-class (BRK.A, BRK.B, BF-B) are kept intact —
        that is the convention Yahoo Finance expects.
        """
        for ticker in ["BRK.A", "BRK.B", "BF-B"]:
            with self.subTest(ticker=ticker):
                self.assertEqual(normalize_ticker(ticker), ticker)

    def test_strips_slash_separators(self):
        """
        Tickers using "/" as a suffix separator (warrants, units, rights from SEC
        13F format) are collapsed to a single token: "GME/WS" → "GMEWS",
        "ACME/U" → "ACMEU" (units), "ACME/RT" → "ACMERT" (rights).
        Share classes that already use dot or dash (BRK.B, BF-B) are unaffected by this
        rule — they are tested separately.
        """
        self.assertEqual(normalize_ticker("GME/WS"), "GMEWS")
        self.assertEqual(normalize_ticker("ACME/U"), "ACMEU")
        self.assertEqual(normalize_ticker("ACME/RT"), "ACMERT")

    def test_empty_input(self):
        """
        Empty or whitespace-only input returns an empty string.
        """
        self.assertEqual(normalize_ticker(""), "")
        self.assertEqual(normalize_ticker("   "), "")

    def test_whitespace_around_ticker_is_trimmed(self):
        """
        Leading/trailing whitespace is stripped.
        """
        self.assertEqual(normalize_ticker("  AAPL  "), "AAPL")


if __name__ == "__main__":
    unittest.main()


class TestNormalizeCompanyName(unittest.TestCase):
    """
    Verifies company-name normalization: trailing security-type descriptors are
    dropped and the comma before a legal-entity suffix is removed, while share
    classes and semantic commas survive untouched.
    """

    def test_strips_trailing_security_descriptors(self):
        cases = [
            ("Grandstand Limited Ordinary Shares", "Grandstand Limited"),
            ("eXp World Holdings Inc Common Stock", "eXp World Holdings Inc"),
            ("Lakefront Biotherapeutics American Depositary Shares", "Lakefront Biotherapeutics"),
            ("Northwind Maritime Group Common Shares", "Northwind Maritime Group"),
            ("Cutter Lane Capital Depositary Shares", "Cutter Lane Capital"),
        ]
        for raw, expected in cases:
            with self.subTest(raw=raw):
                self.assertEqual(normalize_company_name(raw), expected)

    def test_descriptor_stripping_is_case_insensitive(self):
        self.assertEqual(
            normalize_company_name("Velos Holdings Corp. Class A Ordinary shares"),
            "Velos Holdings Corp. Class A",
        )

    def test_keeps_share_class_when_dropping_the_descriptor(self):
        """
        The share class distinguishes the security (Class A vs Class B, and
        mutual-fund classes), so only the descriptor after it is removed.
        """
        cases = [
            ("Ridgeline Compute Class A Common Stock", "Ridgeline Compute Class A"),
            ("Cutter Lane Capital Fund Class A", "Cutter Lane Capital Fund Class A"),
            ("Orbital Rocket Technologies Class B", "Orbital Rocket Technologies Class B"),
        ]
        for raw, expected in cases:
            with self.subTest(raw=raw):
                self.assertEqual(normalize_company_name(raw), expected)

    def test_removes_comma_before_a_legal_suffix(self):
        cases = [
            ("Cutter Lane Capital, Inc.", "Cutter Lane Capital Inc"),
            ("Ridgeline Compute, LP", "Ridgeline Compute LP"),
            ("Orbital Rocket, L.P.", "Orbital Rocket L.P."),
            ("Northwind Maritime, LLC", "Northwind Maritime LLC"),
            ("Grandstand Holdings, Limited", "Grandstand Holdings Limited"),
            ("Velos Industrial, S.A.B. de C.V.", "Velos Industrial S.A.B. de C.V."),
            ("Betterware de Aurora, SAPI de CV", "Betterware de Aurora SAPI de CV"),
        ]
        for raw, expected in cases:
            with self.subTest(raw=raw):
                self.assertEqual(normalize_company_name(raw), expected)

    def test_keeps_semantic_commas(self):
        """
        Commas inside a firm name, a descriptive list or a date are part of the
        name and must survive.
        """
        cases = [
            "Tweedy, Browne Insider + Value ETF",
            "GAMCO Global Gold, Natural Resources & Income Trust",
            "Voya Infrastructure, Industrials and Materials Fund",
            "MicroSectors US Big Oil 3x Leveraged ETNs due February 17, 2045",
        ]
        for raw in cases:
            with self.subTest(raw=raw):
                self.assertEqual(normalize_company_name(raw), raw)

    def test_combines_both_rules(self):
        cases = [
            ("PowerCompute, Inc. Common Stock", "PowerCompute Inc"),
            ("DataMeds AI, Inc. Common Stock", "DataMeds AI Inc"),
            ("Azio AI Holdings, Inc. Common Stock", "Azio AI Holdings Inc"),
        ]
        for raw, expected in cases:
            with self.subTest(raw=raw):
                self.assertEqual(normalize_company_name(raw), expected)

    def test_collapses_whitespace_and_handles_empty(self):
        self.assertEqual(
            normalize_company_name("  Cutter   Lane  Capital  "), "Cutter Lane Capital"
        )
        self.assertEqual(normalize_company_name(""), "")

    def test_leaves_a_plain_name_untouched(self):
        for raw in ("Albemarle Corp", "Alico Inc", "Berkshire Hathaway Class A"):
            with self.subTest(raw=raw):
                self.assertEqual(normalize_company_name(raw), raw)

    def test_strips_a_trailing_period_from_a_single_word_abbreviation(self):
        """
        The file convention is no trailing period ("Inc" outnumbers "Inc." by
        three orders of magnitude).
        """
        cases = [
            ("Cutter Lane Holdings Inc.", "Cutter Lane Holdings Inc"),
            ("Ridgeline Compute Corp.", "Ridgeline Compute Corp"),
            ("Northwind Maritime Ltd.", "Northwind Maritime Ltd"),
            ("Grandstand AG & Co.", "Grandstand AG & Co"),
        ]
        for raw, expected in cases:
            with self.subTest(raw=raw):
                self.assertEqual(normalize_company_name(raw), expected)

    def test_keeps_periods_inside_multi_dot_legal_abbreviations(self):
        """
        Dropping the final dot of "L.P." or "C.V." would mangle the abbreviation.
        """
        cases = [
            "Orbital Rocket L.P.",
            "Velos Industrial S.A.B. de C.V.",
            "Cutter Lane N.V.",
        ]
        for raw in cases:
            with self.subTest(raw=raw):
                self.assertEqual(normalize_company_name(raw), raw)

    def test_comma_and_trailing_period_are_removed_together(self):
        self.assertEqual(
            normalize_company_name("Azio AI Holdings, Inc. Common Stock"),
            "Azio AI Holdings Inc",
        )
