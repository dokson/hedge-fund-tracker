import unittest
from unittest.mock import patch

import pandas as pd

from app.scraper.xml_processor import (
    xml_to_dataframe_4,
    xml_to_dataframe_13f,
    xml_to_dataframe_schedule,
)


def _info(name: str, cusip: str, value: int, shares: int) -> str:
    """
    One 13F infoTable row as XML.
    """
    return (
        f"<infotable><nameofissuer>{name}</nameofissuer><cusip>{cusip}</cusip>"
        f"<value>{value}</value><shrsorprnamt><sshprnamt>{shares}</sshprnamt>"
        "</shrsorprnamt></infotable>"
    )


class TestFilingCorrections(unittest.TestCase):
    """
    A filer's CUSIP mistakes are fixed from the corrections registry at parse time.
    """

    XML = (
        "<informationtable>"
        + _info("UR-ENERGY INC", "N85083108", 18420409, 13252093)
        + _info("VISTRA CORP", "91688R108", 161330, 1000)
        + _info("TERRA INNOVATUM GLOBAL NV", "92840M102", 9039113, 1956518)
        + "</informationtable>"
    )
    CORRECTIONS = {
        ("N85083108", "UR-ENERGY INC"): "91688R108",
        ("91688R108", "VISTRA CORP"): "92840M102",
        ("92840M102", "TERRA INNOVATUM GLOBAL NV"): "N85083108",
    }

    def test_rotated_cusips_are_put_back_on_their_issuers(self):
        """
        Each row takes the CUSIP of the company it names.
        """
        df = xml_to_dataframe_13f(self.XML, corrections=self.CORRECTIONS)
        by_cusip = dict(zip(df["CUSIP"], df["Company"], strict=True))
        self.assertEqual(by_cusip["91688R108"], "UR-ENERGY INC")
        self.assertEqual(by_cusip["92840M102"], "VISTRA CORP")
        self.assertEqual(by_cusip["N85083108"], "TERRA INNOVATUM GLOBAL NV")

    def test_correction_needs_the_filed_name_to_match(self):
        """
        A registry entry never touches a different row that shares the CUSIP.
        """
        df = xml_to_dataframe_13f(
            self.XML, corrections={("91688R108", "SOMETHING ELSE"): "92840M102"}
        )
        self.assertIn("91688R108", set(df["CUSIP"]))

    def test_without_corrections_the_filing_is_kept_as_filed(self):
        """
        No registry, no change: the CSV stays a faithful record of the filing.
        """
        df = xml_to_dataframe_13f(self.XML)
        by_cusip = dict(zip(df["CUSIP"], df["Company"], strict=True))
        self.assertEqual(by_cusip["91688R108"], "VISTRA CORP")


class TestXmlProcessor(unittest.TestCase):
    def test_xml_to_dataframe_13f_empty_filing_does_not_crash(self):
        """
        A filing whose only rows are zeroed-out (filtered to nothing) must return
        an empty DataFrame instead of crashing on the median-price heuristic.
        """
        xml_content = """
        <informationtable>
            <infotable>
                <nameofissuer>Placeholder Co</nameofissuer>
                <cusip>000000000</cusip>
                <value>0</value>
                <shrsorprnamt><sshprnamt>0</sshprnamt></shrsorprnamt>
            </infotable>
        </informationtable>
        """

        df = xml_to_dataframe_13f(xml_content)

        self.assertIsInstance(df, pd.DataFrame)
        self.assertTrue(df.empty)

    def test_xml_to_dataframe_13f_full_dollars_no_scaling(self):
        """
        Tests that values are NOT scaled if the implied share price is realistic (Full Dollars).
        Example: VanEck style.
        """
        # 10,000,000 / 100,000 shares = $100 per share (Realistic price)
        xml_content = """
        <informationtable>
            <infotable>
                <nameofissuer>VanEck Example Corp</nameofissuer>
                <cusip>123456789</cusip>
                <value>10000000</value>
                <shrsorprnamt><sshprnamt>100000</sshprnamt></shrsorprnamt>
            </infotable>
        </informationtable>
        """

        df = xml_to_dataframe_13f(xml_content)

        self.assertIsInstance(df, pd.DataFrame)
        self.assertEqual(len(df), 1)
        # Value should remain exactly as reported
        self.assertEqual(df["Value"][0], 10000000)
        self.assertEqual(df["Shares"][0], 100000)

    def test_xml_to_dataframe_13f_thousands_with_scaling(self):
        """
        Tests that values ARE scaled by 1000 if the implied share price is suspiciously low.
        Example: Duquesne style.
        """
        # 50,000 / 500,000 shares = $0.10 per share (Suspiciously low, likely in thousands)
        # After scaling: $50,000,000 / 500,000 = $100 per share
        xml_content = """
        <informationtable>
            <infotable>
                <nameofissuer>Duquesne Example Inc</nameofissuer>
                <cusip>987654321</cusip>
                <value>50000</value>
                <shrsorprnamt><sshprnamt>500000</sshprnamt></shrsorprnamt>
            </infotable>
        </informationtable>
        """

        df = xml_to_dataframe_13f(xml_content)

        self.assertIsInstance(df, pd.DataFrame)
        self.assertEqual(len(df), 1)
        # Value should be multiplied by 1000
        self.assertEqual(df["Value"][0], 50000 * 1000)
        self.assertEqual(df["Shares"][0], 500000)

    def test_xml_to_dataframe_13f_mixed_portfolio_median_logic(self):
        """
        Tests that the scaling decision is based on the MEDIAN price of the portfolio.
        """
        xml_content = """
        <informationtable>
            <infotable>
                <nameofissuer>Stock A</nameofissuer>
                <cusip>CUSIP1</cusip>
                <value>100</value> <shrsorprnamt><sshprnamt>1000</sshprnamt></shrsorprnamt>
            </infotable>
            <infotable>
                <nameofissuer>Stock B</nameofissuer>
                <cusip>CUSIP2</cusip>
                <value>200</value> <shrsorprnamt><sshprnamt>2000</sshprnamt></shrsorprnamt>
            </infotable>
            <infotable>
                <nameofissuer>Expensive Outlier</nameofissuer>
                <cusip>CUSIP3</cusip>
                <value>5000</value> <shrsorprnamt><sshprnamt>10</sshprnamt></shrsorprnamt>
            </infotable>
        </informationtable>
        """
        # Prices: [0.1, 0.1, 500.0]. Median is 0.1.
        # 0.1 < 0.5 threshold -> Should scale everything by 1000.
        df = xml_to_dataframe_13f(xml_content)

        # 'Stock A' value should be 100 * 1000 = 100,000
        val_a = df.loc[df["Company"] == "Stock A", "Value"].values[0]
        self.assertEqual(val_a, 100000)

    def test_xml_to_dataframe_13f_principal_amount_rows_are_kept(self):
        """
        Positions denominated in principal amount (PRN, debt instruments) are
        part of the filing and must be preserved: the saved per-fund CSV is a
        faithful record, equity-only filtering belongs to the analysis layer.
        """
        xml_content = """
        <informationtable>
            <infotable>
                <nameofissuer>Equity Co</nameofissuer>
                <cusip>CUSIP1</cusip>
                <value>10000000</value>
                <shrsorprnamt><sshprnamt>100000</sshprnamt><sshprnamttype>SH</sshprnamttype></shrsorprnamt>
            </infotable>
            <infotable>
                <nameofissuer>Convertible Bond Co</nameofissuer>
                <cusip>CUSIP2</cusip>
                <value>5000000</value>
                <shrsorprnamt><sshprnamt>5000000</sshprnamt><sshprnamttype>PRN</sshprnamttype></shrsorprnamt>
            </infotable>
        </informationtable>
        """

        df = xml_to_dataframe_13f(xml_content)

        self.assertEqual(len(df), 2)
        self.assertEqual(int(df["Value"].sum()), 15000000)

    def test_xml_to_dataframe_13f_unparseable_numbers_dropped_with_warning(self):
        """
        Rows whose Value or Shares cannot be parsed as numbers must be dropped
        with a warning, not silently zeroed nor crash the parser.
        """
        xml_content = """
        <informationtable>
            <infotable>
                <nameofissuer>Good Co</nameofissuer>
                <cusip>CUSIP1</cusip>
                <value>10000000</value>
                <shrsorprnamt><sshprnamt>100000</sshprnamt></shrsorprnamt>
            </infotable>
            <infotable>
                <nameofissuer>Bad Value Co</nameofissuer>
                <cusip>CUSIP2</cusip>
                <value>12abc</value>
                <shrsorprnamt><sshprnamt>1000</sshprnamt></shrsorprnamt>
            </infotable>
            <infotable>
                <nameofissuer>Bad Shares Co</nameofissuer>
                <cusip>CUSIP3</cusip>
                <value>5000000</value>
                <shrsorprnamt><sshprnamt>garbage</sshprnamt></shrsorprnamt>
            </infotable>
        </informationtable>
        """

        with self.assertLogs("app.scraper.xml_processor", level="WARNING") as captured:
            df = xml_to_dataframe_13f(xml_content)

        self.assertEqual(len(df), 1)
        self.assertEqual(df["Company"][0], "Good Co")
        self.assertTrue(any("2" in message for message in captured.output))


class TestXmlToDataframeSchedule(unittest.TestCase):
    SCHEDULE_XML = """
    <edgarSubmission>
      <formData>
        <coverPageHeader>
          <issuerName>Target Corp</issuerName>
          <issuerCUSIPNumber>123456789</issuerCUSIPNumber>
          <issuerCIK>0001234567</issuerCIK>
          <dateOfEvent>03/15/2026</dateOfEvent>
        </coverPageHeader>
        <coverPageHeaderReportingPersonDetails>
          <reportingPersonName>Big Fund LP</reportingPersonName>
          <rptOwnerCIK>0007654321</rptOwnerCIK>
          <aggregateAmountOwned>500000</aggregateAmountOwned>
          <classPercent>12.7</classPercent>
        </coverPageHeaderReportingPersonDetails>
      </formData>
    </edgarSubmission>
    """

    def test_parses_issuer_and_reporting_person(self):
        """
        A 13D/G filing yields one row per reporting person with the issuer
        metadata, normalized CUSIP, uppercased owner name and parsed date.
        """
        df = xml_to_dataframe_schedule(self.SCHEDULE_XML)

        self.assertEqual(len(df), 1)
        row = df.iloc[0]
        self.assertEqual(row["Company"], "Target Corp")
        self.assertEqual(row["CUSIP"], "123456789")
        self.assertEqual(row["CIK"], "0001234567")
        self.assertEqual(row["Shares"], 500000)
        self.assertEqual(row["Owner_CIK"], "0007654321")
        self.assertEqual(row["Owner"], "BIG FUND LP")
        self.assertEqual(row["Date"], pd.Timestamp("2026-03-15"))
        self.assertEqual(row["Class_Pct"], 12.7)

    def test_class_percent_is_absent_when_not_reported(self):
        """
        Older schedule schemas omit the percentage of class; it must parse as
        missing rather than zero, which would read as a real 0% stake.
        """
        xml = self.SCHEDULE_XML.replace("<classPercent>12.7</classPercent>", "")

        df = xml_to_dataframe_schedule(xml)

        self.assertTrue(pd.isna(df.iloc[0]["Class_Pct"]))

    NEW_SCHEMA_XML = """
    <edgarSubmission>
      <formData>
        <coverPageHeader>
          <dateOfEvent>04/22/2026</dateOfEvent>
          <issuerInfo>
            <issuerCIK>0001234567</issuerCIK>
            <issuerCusips><issuerCusipNumber>123456789</issuerCusipNumber></issuerCusips>
            <issuerName>Target Corp</issuerName>
          </issuerInfo>
        </coverPageHeader>
        <reportingPersons>
          <reportingPersonInfo>
            <reportingPersonCIK>0007654321</reportingPersonCIK>
            <reportingPersonName>Doe Jane</reportingPersonName>
            <aggregateAmountOwned>54364.00</aggregateAmountOwned>
          </reportingPersonInfo>
        </reportingPersons>
      </formData>
    </edgarSubmission>
    """

    def test_new_schema_reporting_person_cik_is_parsed(self):
        """
        The current EDGAR schedule schema nests the owner CIK in
        <reportingPersonCIK>; it must populate Owner_CIK so CIK-based fund
        matching works when the owner name differs from the denomination.
        """
        df = xml_to_dataframe_schedule(self.NEW_SCHEMA_XML)

        self.assertEqual(len(df), 1)
        row = df.iloc[0]
        self.assertEqual(row["Owner_CIK"], "0007654321")
        self.assertEqual(row["Owner"], "DOE JANE")
        self.assertEqual(row["Shares"], 54364)
        self.assertEqual(row["CUSIP"], "123456789")

    def test_non_numeric_shares_coerced_to_zero(self):
        """
        A missing/garbage aggregate amount becomes 0 rather than crashing the
        integer cast.
        """
        xml = self.SCHEDULE_XML.replace("<aggregateAmountOwned>500000", "<aggregateAmountOwned>n/a")

        df = xml_to_dataframe_schedule(xml)

        self.assertEqual(df.iloc[0]["Shares"], 0)


@patch("app.scraper.xml_processor.TickerResolver.assign_cusip", side_effect=lambda df: df)
class TestXmlToDataframe4(unittest.TestCase):
    FORM4_XML = """
    <ownershipDocument>
      <issuer>
        <issuerName>Insider Co</issuerName>
        <issuerTradingSymbol>INSD</issuerTradingSymbol>
        <issuerCik>0002223334</issuerCik>
      </issuer>
      <periodOfReport>2026-04-10</periodOfReport>
      <nonDerivativeTable>
        <nonDerivativeTransaction>
          <postTransactionAmounts>
            <sharesOwnedFollowingTransaction><value>12000</value></sharesOwnedFollowingTransaction>
          </postTransactionAmounts>
          <ownershipNature>
            <directOrIndirectOwnership><value>D</value></directOrIndirectOwnership>
          </ownershipNature>
        </nonDerivativeTransaction>
      </nonDerivativeTable>
      <reportingOwner>
        <reportingOwnerId>
          <rptOwnerCik>0005556667</rptOwnerCik>
          <rptOwnerName>Jane Insider</rptOwnerName>
        </reportingOwnerId>
      </reportingOwner>
    </ownershipDocument>
    """

    def test_parses_final_holding_and_owner(self, _assign):
        """
        Form 4 yields the post-transaction share count for the reporting
        owner with normalized ticker and parsed period-of-report date.
        """
        df = xml_to_dataframe_4(self.FORM4_XML)

        self.assertEqual(len(df), 1)
        row = df.iloc[0]
        self.assertEqual(row["Company"], "Insider Co")
        self.assertEqual(row["Ticker"], "INSD")
        self.assertEqual(row["CIK"], "0002223334")
        self.assertEqual(row["Shares"], 12000)
        self.assertEqual(row["Owner_CIK"], "0005556667")
        self.assertEqual(row["Owner"], "JANE INSIDER")
        self.assertEqual(row["Date"], pd.Timestamp("2026-04-10"))

    def test_comma_grouped_share_count_is_parsed(self, _assign):
        """
        A comma-grouped share count is a formatting quirk, not bad data: it
        must parse to the numeric value instead of crashing the batch.
        """
        xml = self.FORM4_XML.replace("<value>12000</value>", "<value>12,000</value>")

        df = xml_to_dataframe_4(xml)

        self.assertEqual(df.iloc[0]["Shares"], 12000)

    def test_garbage_share_count_skips_item_not_filing(self, _assign):
        """
        A non-numeric share count skips that item with a warning; the filing
        (and the rest of the batch) survives instead of raising ValueError.
        """
        xml = self.FORM4_XML.replace("<value>12000</value>", "<value>see footnote</value>")

        df = xml_to_dataframe_4(xml)

        self.assertEqual(len(df), 1)
        self.assertEqual(df.iloc[0]["Shares"], 0)

    def test_sums_direct_and_indirect_holdings(self, _assign):
        """
        Holdings under distinct ownership natures (direct + indirect) are
        summed into the owner's total post-transaction position.
        """
        xml = self.FORM4_XML.replace(
            "</nonDerivativeTable>",
            """
            <nonDerivativeHolding>
              <postTransactionAmounts>
                <sharesOwnedFollowingTransaction><value>3000</value></sharesOwnedFollowingTransaction>
              </postTransactionAmounts>
              <ownershipNature>
                <directOrIndirectOwnership><value>I</value></directOrIndirectOwnership>
                <natureOfOwnership><value>By Trust</value></natureOfOwnership>
              </ownershipNature>
            </nonDerivativeHolding>
            </nonDerivativeTable>
            """,
        )

        df = xml_to_dataframe_4(xml)

        self.assertEqual(df.iloc[0]["Shares"], 15000)

    @staticmethod
    def _with_titled_holding(xml, main_title, extra_title, extra_shares, before=False):
        """
        Titles the base transaction and adds a direct holding of another security title,
        placed before or after it in the non-derivative table.
        """
        xml = xml.replace(
            "<nonDerivativeTransaction>",
            f"<nonDerivativeTransaction><securityTitle><value>{main_title}</value></securityTitle>",
        )
        holding = f"""
            <nonDerivativeHolding>
              <securityTitle><value>{extra_title}</value></securityTitle>
              <postTransactionAmounts>
                <sharesOwnedFollowingTransaction><value>{extra_shares}</value></sharesOwnedFollowingTransaction>
              </postTransactionAmounts>
              <ownershipNature>
                <directOrIndirectOwnership><value>I</value></directOrIndirectOwnership>
                <natureOfOwnership><value>By Fund</value></natureOfOwnership>
              </ownershipNature>
            </nonDerivativeHolding>
            """
        if before:
            return xml.replace("<nonDerivativeTable>", "<nonDerivativeTable>" + holding)
        return xml.replace("</nonDerivativeTable>", holding + "</nonDerivativeTable>")

    def test_other_security_classes_are_not_summed(self, _assign):
        """
        A preferred holding reported alongside common stock is a different
        security: only the common position counts.
        """
        xml = self._with_titled_holding(
            self.FORM4_XML, "Common Stock", "Series A Preferred Stock", 5000
        )

        self.assertEqual(xml_to_dataframe_4(xml).iloc[0]["Shares"], 12000)

    def test_common_stock_wins_even_when_listed_after_another_class(self, _assign):
        """
        The common position is chosen regardless of the order of the rows.
        """
        xml = self._with_titled_holding(
            self.FORM4_XML, "Common Stock", "Convertible Preferred Stock", 5000, before=True
        )

        self.assertEqual(xml_to_dataframe_4(xml).iloc[0]["Shares"], 12000)

    def test_distinct_common_classes_prefer_class_a(self, _assign):
        """
        Two common classes are distinct securities: Class A is kept even when an
        (often unlisted) Class B is listed first, and the ambiguity is logged.
        """
        xml = self._with_titled_holding(
            self.FORM4_XML, "Class A Common Stock", "Class B Common Stock", 3000, before=True
        )

        with self.assertLogs("app.scraper.xml_processor", level="WARNING"):
            self.assertEqual(xml_to_dataframe_4(xml).iloc[0]["Shares"], 12000)

    def test_undesignated_common_class_wins_over_a_designated_one(self, _assign):
        """
        Plain common stock (no class designator) is preferred over a lettered class.
        """
        xml = self._with_titled_holding(
            self.FORM4_XML, "Common Stock", "Class B Common Stock", 3000, before=True
        )

        with self.assertLogs("app.scraper.xml_processor", level="WARNING"):
            self.assertEqual(xml_to_dataframe_4(xml).iloc[0]["Shares"], 12000)

    def test_without_class_a_the_first_common_class_is_kept(self, _assign):
        """
        With neither plain common nor Class A, the first common class listed is kept.
        """
        xml = self._with_titled_holding(
            self.FORM4_XML, "Class B Common Stock", "Class C Common Stock", 3000
        )

        self.assertEqual(xml_to_dataframe_4(xml).iloc[0]["Shares"], 12000)

    def test_title_wording_variants_of_one_class_are_summed(self, _assign):
        """
        The same common class written with and without its par value is one
        security, so its direct and indirect positions are still summed.
        """
        xml = self._with_titled_holding(
            self.FORM4_XML, "Common Stock", "Common Stock, par value $0.01", 3000
        )

        self.assertEqual(xml_to_dataframe_4(xml).iloc[0]["Shares"], 15000)


if __name__ == "__main__":
    unittest.main()
