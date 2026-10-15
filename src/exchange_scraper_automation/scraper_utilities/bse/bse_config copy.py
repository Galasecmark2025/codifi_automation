# # =========================================================
# # BSE CONFIGURATION
# # =========================================================
# BSE_API_URL = "https://api.bseindia.com/" "BseIndiaAPI/api/GetBhavcopydata/w?flag=0"


# # ---------------------------------------------------------
# # BSE HEADERS
# # ---------------------------------------------------------
# BSE_HEADERS = {
#     "Accept": "application/json, text/plain, */*",
#     "Accept-Language": "en-US,en;q=0.9,en-IN;q=0.8",
#     "Origin": "https://www.bseindia.com",
#     "Referer": "https://www.bseindia.com/",
#     "User-Agent": (
#         "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
#         "AppleWebKit/537.36 (KHTML, like Gecko) "
#         "Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0"
#     ),
# }


# # ---------------------------------------------------------
# # BSE FILE TYPES
# # ---------------------------------------------------------
# #
# # The API supplies the actual filename.
# # We only configure:
# #
# # file_type     -> value expected from BSE API
# # download_path -> base URL for that file
# # segment       -> business segment
# # data_type     -> type of data
# # extension     -> expected downloaded extension
# #
# # ---------------------------------------------------------
# BSE_REPORTS = [
#     {
#         "file_type": "EQ",
#         "segment": "EQ",
#         "data_type": "Bhavcopy",
#         "download_path": "https://www.bseindia.com/" "download/BhavCopy/Equity/",
#         "file_extension": ".csv",
#         # Add exact manager-approved table name later
#         "table_name": "tbl_TempBhavCopyBSEEQ",
#     },
#     {
#         "file_type": "COM",
#         "segment": "COM",
#         "data_type": "Bhavcopy",
#         "download_path": "https://www.bseindia.com/" "download/BhavCopy/Commodity/Csv/",
#         "file_extension": ".csv",
#         "table_name": "tbl_TempBhavCopyBSECO",
#     },
#     {
#         "file_type": "CUR",
#         "segment": "CUR",
#         "data_type": "Bhavcopy",
#         "download_path": "https://www.bseindia.com/" "bsedata/CIML_bhavcopy/",
#         "file_extension": ".csv",
#         "table_name": "tbl_TempBhavCopyBSECU",
#     },
#     {
#         "file_type": "EQD",
#         "segment": "FO",
#         "data_type": "Bhavcopy",
#         "download_path": "https://www.bseindia.com/" "download/BhavCopy/Derivative/",
#         "file_extension": ".csv",
#         "zip_file": "EQD_CO*.csv",
#         "table_name": "tbl_TempBhavCopyBSEFO",
#     },
#     {
#         "file_type": "EQ_SCRIPMASTER",
#         "segment": "EQ",
#         "data_type": "ScripMaster",
#         "file_name": "scrip.zip",
#         "url": "https://beta.bseindia.com/downloads/Help/file/scrip.zip",
#         "file_extension": ".zip",
#         "zip_file": "BSE_EQ_SCRIP*.csv",
#         "table_name": "tbl_TempScripMasterBSEEQ",
#     },
#     {
#         "file_type": "CUR_CONTRACTMASTER",
#         "segment": "CUR",
#         "data_type": "ContractMaster",
#         "file_name": "Master.zip",
#         "url": "https://www.bseindia.com/downloads1/Master.zip",
#         "file_extension": ".zip",
#         "zip_file": "BSE_BFX_CONTRACT_*.csv",
#         "table_name": "tbl_TempContractMasterBSECU",
#     },
#     {
#         "file_type": "CUR_SPREAD_SCRIPMASTER",
#         "segment": "CUR",
#         "data_type": "SpreadScripMaster",
#         "file_name": "Master.zip",
#         "url": "https://www.bseindia.com/downloads1/Master.zip",
#         "file_extension": ".zip",
#         "zip_file": "BSE_BFX_SPDCONTRACT_*.csv",
#         "table_name": "tbl_TempSpreadScripMasterBSECU",
#     },
#     {
#         "file_type": "COM_CONTRACTMASTER",
#         "segment": "COM",
#         "data_type": "ContractMaster",
#         "file_name": "COMMaster.zip",
#         "url": "https://www.bseindia.com/downloads1/COMMaster.zip",
#         "file_extension": ".zip",
#         "zip_file": "BCX_CO*.csv",
#         "table_name": "tbl_TempContractMasterBSECO",
#         "skip_rows": 1,
#     },
#     {
#         "file_type": "FO_CONTRACTMASTER",
#         "segment": "FO",
#         "data_type": "ContractMaster",
#         "file_name": "CO.zip",
#         "url": "https://www.bseindia.com/downloads/Help/file/CO.zip",
#         "file_extension": ".zip",
#         "zip_file": "BSE_EQD*.csv",
#         "table_name": "tbl_TempContractMasterBSEFO",
#     },
#     {
#         "file_type": "SLBM_SCRIPMASTER",
#         "segment": "SLBM",
#         "data_type": "ScripMaster",
#         "file_name": "SLB_Securities.zip",
#         "url": "https://www.bseindia.com/downloads1/SLB_Securities.zip",
#         "file_extension": ".zip",
#         # We will determine the exact file inside the ZIP.
#         "zip_file": "all",
#         "table_name": "tbl_TempScripMasterBSESLBM",
#     },
# ]

# # =========================================================
# # BSE SLBM
# # =========================================================
# BSE_SLBM = {
#     "segment": "SLBM",
#     "data_type": "Bhavcopy",
#     "download_path": "https://www.bseindia.com/" "bsedata/SLBNEWBhavCopy/",
#     "api_key": "dsSLBNEW",
#     "api_filename_key": "FilePath",
#     "file_prefix": "BSESLB_BhavCopy_",
#     "file_extension": ".csv",
#     "table_name": "tbl_TempBhavCopyBSESLB",
#     "zip_file": "all",
# }

# # =========================================================
# # BSE VAR
# # =========================================================
# BSE_VAR = {
#     "api_url": ("https://api.bseindia.com/" "BseIndiaAPI/api/EQReports_VarELM_ng/w"),
#     "api_key": "Table",
#     "file_name_key": "File_Name",
#     "file_path_key": "File_Path",
#     "file_name": "VAR MARGIN",
#     "file_extension": ".zip",
#     "zip_file": "current_date",
#     "segment": "EQ",
#     "data_type": "Margin",
#     "table_name": "tbl_TempMarginDetailBSEEQ",
# }

# =========================================================
# BSE CONFIGURATION
# =========================================================

BSE_API_URL = "https://api.bseindia.com/" "BseIndiaAPI/api/GetBhavcopydata/w?flag=0"


# ---------------------------------------------------------
# BSE HEADERS
# ---------------------------------------------------------

BSE_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9,en-IN;q=0.8",
    "Origin": "https://www.bseindia.com",
    "Referer": "https://www.bseindia.com/",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0"
    ),
}


# =========================================================
# BSE REPORTS
# =========================================================
#
# data_type values used by run_selection.py:
#
#   Bhavcopy
#   ScripMaster
#   SpreadScripMaster
#   ContractMaster
#
# Static/direct files use:
#
#   file_name
#   url
#
# API-based files use:
#
#   file_type
#   download_path
#
# zip_file:
#   Identifies the required file inside the downloaded ZIP.
#
# =========================================================

# =========================================================
# BSE CONFIGURATION
# =========================================================

BSE_API_URL = "https://api.bseindia.com/" "BseIndiaAPI/api/GetBhavcopydata/w?flag=0"


# ---------------------------------------------------------
# BSE HEADERS
# ---------------------------------------------------------

BSE_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9,en-IN;q=0.8",
    "Origin": "https://www.bseindia.com",
    "Referer": "https://www.bseindia.com/",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0"
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
        "table_name": "tbl_TempContractMasterBSECU",
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
        "zip_file": "BCX_CO*.csv",
        "table_name": "tbl_TempContractMasterBSECO",
        "skip_rows": 1,
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
        "zip_file": "BSE_EQD*.csv",
        "table_name": "tbl_TempContractMasterBSEFO",
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
