import unittest
from unittest.mock import patch

import pandas as pd

from app.scraper.xml_processor import (
    xml_to_dataframe_4,
    xml_to_dataframe_13f,
    xml_to_dataframe_schedule,
)


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


if __name__ == "__main__":
    unittest.main()
