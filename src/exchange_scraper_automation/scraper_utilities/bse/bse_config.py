# =========================================================
# BSE CONFIGURATION
# =========================================================

BSE_API_URL = "https://api.bseindia.com/" "BseIndiaAPI/api/GetBhavcopydata/w?flag=0"


# ---------------------------------------------------------
# BSE HEADERS
# ---------------------------------------------------------

BSE_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": "https://www.bseindia.com",
    "Referer": "https://www.bseindia.com/",
    "Priority": "u=1, i",
    "Sec-CH-UA": (
        '"Chromium";v="154", ' '"Google Chrome";v="154", ' '"Not A(Brand";v="99"'
    ),
    "Sec-CH-UA-Mobile": "?0",
    "Sec-CH-UA-Platform": '"Windows"',
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-site",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/154.0.0.0 Safari/537.36"
    ),
}


# =========================================================
# BSE REPORTS
# =========================================================

BSE_REPORTS = [
    # =====================================================
    # BSE EQUITY BHAVCOPY
    # =====================================================
    {
        "file_type": "EQ",
        "segment": "EQ",
        "data_type": "Bhavcopy",
        "download_path": ("https://www.bseindia.com/" "download/BhavCopy/Equity/"),
        "file_extension": ".csv",
        "table_name": "tbl_TempBhavCopyBSEEQ",
    },
    # =====================================================
    # BSE COMMODITY BHAVCOPY
    # =====================================================
    {
        "file_type": "COM",
        "segment": "COM",
        "data_type": "Bhavcopy",
        "download_path": (
            "https://www.bseindia.com/" "download/BhavCopy/Commodity/Csv/"
        ),
        "file_extension": ".csv",
        "table_name": "tbl_TempBhavCopyBSECO",
    },
    # =====================================================
    # BSE CURRENCY BHAVCOPY
    # =====================================================
    {
        "file_type": "CUR",
        "segment": "CUR",
        "data_type": "Bhavcopy",
        "download_path": ("https://www.bseindia.com/" "bsedata/CIML_bhavcopy/"),
        "file_extension": ".csv",
        "table_name": "tbl_TempBhavCopyBSECU",
    },
    # =====================================================
    # BSE F&O BHAVCOPY
    # =====================================================
    {
        "file_type": "EQD",
        "segment": "FO",
        "data_type": "Bhavcopy",
        "download_path": ("https://www.bseindia.com/" "download/BhavCopy/Derivative/"),
        "file_extension": ".csv",
        "zip_file": "EQD_CO*.csv",
        "table_name": "tbl_TempBhavCopyBSEFO",
    },
    # =====================================================
    # BSE EQUITY SCRIPMASTER
    # =====================================================
    {
        "file_type": "EQ_SCRIPMASTER",
        "segment": "EQ",
        "data_type": "ScripMaster",
        "file_name": "scrip.zip",
        "url": ("https://beta.bseindia.com/" "downloads/Help/file/scrip.zip"),
        "file_extension": ".zip",
        "zip_file": "BSE_EQ_SCRIP*.csv",
        "table_name": "tbl_TempScripMasterBSEEQ",
    },
    # =====================================================
    # BSE CURRENCY SCRIPMASTER
    # =====================================================
    #
    # The previous working implementation used:
    #
    # Master.zip
    #   -> BSE_BFX_CONTRACT_*.csv
    #
    # and populated tbl_TempScripMasterBSECU.
    #
    # =====================================================
    {
        "file_type": "CUR_SCRIPMASTER",
        "segment": "CUR",
        "data_type": "ScripMaster",
        "file_name": "Master.zip",
        "url": ("https://www.bseindia.com/" "downloads1/Master.zip"),
        "file_extension": ".zip",
        "zip_file": "BSE_BFX_CONTRACT_*.csv",
        "table_name": "tbl_TempScripMasterBSECU",
    },
    # =====================================================
    # BSE CURRENCY SPREAD SCRIPMASTER
    # =====================================================
    {
        "file_type": "CUR_SPREAD_SCRIPMASTER",
        "segment": "CUR",
        "data_type": "SpreadScripMaster",
        "file_name": "Master.zip",
        "url": ("https://www.bseindia.com/" "downloads1/Master.zip"),
        "file_extension": ".zip",
        "zip_file": "BSE_BFX_SPDCONTRACT_*.csv",
        "table_name": "tbl_TempSpreadScripMasterBSECU",
    },
    # =====================================================
    # BSE CURRENCY CONTRACT MASTER
    # =====================================================
    #
    # Keep this separate from CUR ScripMaster.
    #
    # =====================================================
    {
        "file_type": "CUR_CONTRACTMASTER",
        "segment": "CUR",
        "data_type": "ContractMaster",
        "file_name": "Master.zip",
        "url": ("https://www.bseindia.com/" "downloads1/Master.zip"),
        "file_extension": ".zip",
        "zip_file": "BSE_BFX_CONTRACT_*.csv",
        "table_name": "tbl_TempScripMasterBSECU",
    },
    # =====================================================
    # BSE COMMODITY CONTRACT MASTER
    # =====================================================
    {
        "file_type": "COM_CONTRACTMASTER",
        "segment": "COM",
        "data_type": "ContractMaster",
        "file_name": "COMMaster.zip",
        "url": ("https://www.bseindia.com/" "downloads1/COMMaster.zip"),
        "file_extension": ".zip",
        "zip_file": "BSE_BCX_CONTRACT*.csv",
        "table_name": "tbl_TempScripMasterBSECO",
    },
    # =====================================================
    # BSE F&O CONTRACT MASTER
    # =====================================================
    {
        "file_type": "FO_CONTRACTMASTER",
        "segment": "FO",
        "data_type": "ContractMaster",
        "file_name": "CO.zip",
        "url": ("https://www.bseindia.com/" "downloads/Help/file/CO.zip"),
        "file_extension": ".zip",
        "zip_file": "BSE_EQD_CONTRACT*.csv",
        "table_name": "tbl_TempScripMasterBSEFO",
    },
    # =====================================================
    # BSE SLBM SCRIPMASTER
    # =====================================================
    {
        "file_type": "SLBM_SCRIPMASTER",
        "segment": "SLBM",
        "data_type": "ScripMaster",
        "file_name": "SLB_Securities.zip",
        "url": ("https://www.bseindia.com/" "downloads1/SLB_Securities.zip"),
        "file_extension": ".zip",
        "zip_file": "all",
        "table_name": "tbl_TempScripMasterBSESLBM",
    },
]


# =========================================================
# BSE SLBM BHAVCOPY
# =========================================================

BSE_SLBM = {
    "segment": "SLBM",
    "data_type": "Bhavcopy",
    "download_path": ("https://www.bseindia.com/" "bsedata/SLBNEWBhavCopy/"),
    "api_key": "dsSLBNEW",
    "api_filename_key": "FilePath",
    "file_prefix": "BSESLB_BhavCopy_",
    "file_extension": ".csv",
    "table_name": "tbl_TempBhavCopyBSESLB",
    "zip_file": "all",
}


# =========================================================
# BSE VAR / MARGIN
# =========================================================

BSE_VAR = {
    "api_url": ("https://api.bseindia.com/" "BseIndiaAPI/api/EQReports_VarELM_ng/w"),
    "api_key": "Table",
    "file_name_key": "File_Name",
    "file_path_key": "File_Path",
    "file_name": "VAR MARGIN",
    "file_extension": ".zip",
    "zip_file": "current_date",
    "segment": "EQ",
    "data_type": "Margin",
    "table_name": "tbl_TempMarginDetailBSEEQ",
}
