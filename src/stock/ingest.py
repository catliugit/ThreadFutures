"""Bronze layer: download UCI Online Retail II and land it as Parquet.

Source: Chen, D. (2012). Online Retail II [Dataset]. UCI Machine Learning Repository.
https://doi.org/10.24432/C5CG6D  Licence: CC BY 4.0.

About 1.07m invoice lines from a UK online retailer, Dec 2009 to Dec 2011. It is not a
fashion retailer, so Thread Futures uses it to build and test the stock-analytics
methods on real sales behaviour (launches, decay, markdowns, returns, seasonality).
"""
from __future__ import annotations

import sys
import urllib.request
import zipfile
from pathlib import Path

import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw" / "retail"
URL = "https://archive.ics.uci.edu/static/public/502/online+retail+ii.zip"
OUT = RAW / "transactions.parquet"


def download() -> Path:
    RAW.mkdir(parents=True, exist_ok=True)
    xlsx = RAW / "online_retail_II.xlsx"
    if not xlsx.exists():
        zpath = RAW / "online_retail_ii.zip"
        urllib.request.urlretrieve(URL, zpath)
        with zipfile.ZipFile(zpath) as z:
            z.extractall(RAW)
    return xlsx


def land(xlsx: Path, out: Path = OUT) -> Path:
    sheets = pd.read_excel(xlsx, sheet_name=None, dtype={"Invoice": str, "StockCode": str, "Customer ID": "Int64"})
    df = pd.concat(sheets.values(), ignore_index=True)
    df.columns = ["invoice", "stock_code", "description", "quantity", "invoice_ts", "unit_price", "customer_id", "country"]
    con = duckdb.connect()
    con.register("df", df)
    con.execute(f"COPY df TO '{out.as_posix()}' (FORMAT PARQUET)")
    return out


def main() -> None:
    if OUT.exists() and "--force" not in sys.argv:
        print(f"{OUT} exists; use --force to rebuild")
        return
    out = land(download())
    n = duckdb.connect().execute(f"select count(*) from '{out.as_posix()}'").fetchone()[0]
    print(f"landed {n:,} rows -> {out}")


if __name__ == "__main__":
    main()
