NSE_PAGE_URL = "https://www.nseindia.com/all-reports"
NSE_DERIVATIVES_PAGE_URL = "https://www.nseindia.com/all-reports-derivatives"

# ---------------------------------------------------------
# NSE CAPITAL MARKET TABS
# ---------------------------------------------------------
CAPITAL_MARKET_TABS = {
    "equities": "cr_equities",
    "slbm": "cr_ssbs",
}

# ---------------------------------------------------------
# NSE DERIVATIVES TABS
# ---------------------------------------------------------
DERIVATIVE_MARKET_TABS = {
    "equity": "cr_derv_equities",
    "currency": "cr_derv_currency",
    "commodity": "cr_derv_commodity",
}


# ---------------------------------------------------------
# NSE REPORTS
# ---------------------------------------------------------
NSE_REPORTS = [
    # =====================================================
    # EQUITIES & SME
    # =====================================================
    {
        "market": "capital_market",
        "tab": CAPITAL_MARKET_TABS["equities"],
        "section": "equities",
        "segment": "EQ",
        "data_type": "Margin",
        "report_label": "VaR Begin Day File",
        "file_extension": ".dat",
        # Safety validation
        "url_contains": "/archives/nsccl/var/",
        "filename_prefix": "C_VAR1_",
        "table_name": "tbl_TempMarginDetailNSEEQ",
    },
    {
        "market": "capital_market",
        "tab": CAPITAL_MARKET_TABS["equities"],
        "section": "equities",
        "segment": "EQ",
        "data_type": "Bhavcopy",
        "report_label": "CM-UDiFF Common Bhavcopy Final (zip)",
        "file_extension": ".zip",
        # Safety validation
        "url_contains": "/content/cm/",
        "filename_prefix": "BhavCopy_NSE_CM_",
        "table_name": "tbl_TempBhavCopyNSEEQ",
    },
    {
        "market": "capital_market",
        "tab": CAPITAL_MARKET_TABS["equities"],
        "section": "equities",
        "segment": "EQ",
        "data_type": "ScripMaster",
        "report_label": "CM - MII - Security File (.gz) (NSE Listed and BSE Exclusive securities)",
        "file_extension": ".gz",
        # Safety validation
        "url_contains": "/content/cm/interop/",
        "filename_prefix": "NSE_CM_security_",
        "table_name": "tbl_TempScripMasterNSEEQ",
    },
    # =====================================================
    # SECURITIES LENDING & BORROWING
    # =====================================================
    {
        "market": "capital_market",
        "tab": CAPITAL_MARKET_TABS["slbm"],
        "section": "slb",
        "segment": "SLBM",
        "data_type": "Margin",
        "report_label": "VaR Begin Day File",
        "file_extension": ".dat",
        # IMPORTANT:
        # SLBM VaR must NEVER use the Equity VaR URL.
        "url_contains": "/archives/slbs/var/",
        "filename_prefix": "C_VAR1_SLB_",
        "table_name": "tbl_TempMarginDetailNSESLB",
    },
    {
        "market": "capital_market",
        "tab": CAPITAL_MARKET_TABS["slbm"],
        "section": "slb",
        "segment": "SLBM",
        "data_type": "Bhavcopy",
        "report_label": "Bhavcopy Download (DAT)",
        "file_extension": ".dat",
        # Safety validation
        "url_contains": "/archives/slbs/bhavcopy/",
        "filename_prefix": "SLBM_BC_",
        "table_name": "tbl_TempBhavCopyNSESLB",
        "headers": [
            "security_name",
            "symbol",
            "series",
            "expiry_date",
            "settlement_type",
            "open_price",
            "high_price",
            "low_price",
            "close_price",
            "last_price",
            "blank_field",
            "total_traded_quantity",
            "total_traded_value",
            "fifty_two_week_high",
            "fifty_two_week_low",
            "trade_date",
            "number_of_trades",
        ],
    },
    {
        "market": "capital_market",
        "tab": CAPITAL_MARKET_TABS["slbm"],
        "section": "slb",
        "segment": "SLBM",
        "data_type": "ScripMaster",
        "report_label": "List of eligible securities in SLBS(csv)",
        "file_extension": ".csv",
        # Safety validation
        "url_contains": "/archives/slbs/seclist/",
        "filename_prefix": "SLB_ELG_SEC_",
        "table_name": "tbl_TempScripMasterNSESLB",
    },
    # =====================================================
    # EQUITY DERIVATIVES
    # =====================================================
    {
        "market": "derivatives",
        "tab": DERIVATIVE_MARKET_TABS["equity"],
        "section": "equity",
        "segment": "FO",
        "data_type": "Bhavcopy",
        "report_label": "F&O-UDiFF Common Bhavcopy Final (zip)",
        "file_extension": ".zip",
        # Safety validation
        "url_contains": "/content/fo/",
        "filename_prefix": "BhavCopy_NSE_FO_",
        "table_name": "tbl_TempBhavCopyNSEFO",
    },
    {
        "market": "derivatives",
        "tab": DERIVATIVE_MARKET_TABS["equity"],
        "section": "equity",
        "segment": "FO",
        "data_type": "ScripMaster",
        "report_label": "F&O-MII – Contract File (.gz) (NSE and BSE Exclusive Contract)",
        "file_extension": ".gz",
        # Safety validation
        "url_contains": "/content/fo/interop/",
        "filename_prefix": "NSE_FO_contract_",
        "table_name": "tbl_TempScripMasterNSEFO",
    },
    {
        "market": "derivatives",
        "tab": DERIVATIVE_MARKET_TABS["equity"],
        "section": "equity",
        "segment": "FO",
        "data_type": "Margin",
        "report_label": "F&O-Exposure Limit file (csv)",
        "file_extension": ".csv",
        # Safety validation
        "url_contains": "/archives/exp_lim/",
        "filename_prefix": "ael_",
        "table_name": "tbl_TempMarginDetailNSEFO",
    },
    # =====================================================
    # CURRENCY DERIVATIVES
    # =====================================================
    {
        "market": "derivatives",
        "tab": DERIVATIVE_MARKET_TABS["currency"],
        "section": "currency",
        "segment": "CUR",
        "data_type": "ScripMaster",
        "report_label": "CD-MII - Contract Files (.gz)",
        "file_extension": ".gz",
        # Safety validation
        "url_contains": "/content/cd/",
        "filename_prefix": "NSE_CD_contract_",
        "table_name": "tbl_TempScripMasterNSECU",
    },
    {
        "market": "derivatives",
        "tab": DERIVATIVE_MARKET_TABS["currency"],
        "section": "currency",
        "segment": "CUR",
        "data_type": "ScripMaster",
        "report_label": "CD-MII - Spd Contract Files (.gz)",
        "file_extension": ".gz",
        # Safety validation
        "url_contains": "/content/cd/",
        "filename_prefix": "NSE_CD_spdcontract_",
        "table_name": "tbl_TempSpreadScripMasterNSECU",
    },
    {
        "market": "derivatives",
        "tab": DERIVATIVE_MARKET_TABS["currency"],
        "section": "currency",
        "segment": "CUR",
        "data_type": "Bhavcopy",
        "report_label": "CD-UDiFF Common Bhavcopy Final (zip)",
        "file_extension": ".zip",
        # Safety validation
        "url_contains": "/archives/cd/bhav/",
        "filename_prefix": "BhavCopy_NSE_CD_",
        "table_name": "tbl_TempBhavCopyNSECU",
    },
    # =====================================================
    # COMMODITY DERIVATIVES
    # =====================================================
    {
        "market": "derivatives",
        "tab": DERIVATIVE_MARKET_TABS["commodity"],
        "section": "commodity",
        "segment": "COM",
        "data_type": "ScripMaster",
        "report_label": "COM-MII - Contract Files (.gz)",
        "file_extension": ".gz",
        # Safety validation
        "url_contains": "/content/com/",
        "filename_prefix": "NSE_COM_contract_",
        "table_name": "tbl_TempScripMasterNSECO",
    },
    {
        "market": "derivatives",
        "tab": DERIVATIVE_MARKET_TABS["commodity"],
        "section": "commodity",
        "segment": "COM",
        "data_type": "Bhavcopy",
        "report_label": "COM-UDiFF Common Bhavcopy Final (zip)",
        "file_extension": ".zip",
        # Safety validation
        "url_contains": "/content/com/",
        "filename_prefix": "BhavCopy_NSE_CO_",
        "table_name": "tbl_TempBhavCopyNSECO",
    },
]

NSE_MARGIN_TABLES = {
    # Generated by scrape_currency_margin()
    "NSE_CUR_Margin.csv": "tbl_TempMarginDetailNSECU",
    # Will be generated later by commodity margin scraper
    "NSE_COM_Margin.csv": "tbl_TempMarginDetailNSECO",
}
