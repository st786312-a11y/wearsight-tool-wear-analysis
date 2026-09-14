"""Replace the active case database with labelled images from 磨耗%.zip."""

from __future__ import annotations

import csv
import io
import json
import shutil
import sys
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "backend" / "data"


def main(archive_path: Path) -> None:
    if not archive_path.exists():
        raise FileNotFoundError(archive_path)

    staging = DATA / ".wear_percent_staging"
    target = DATA / "wear_percent_cases"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)

    records: list[dict] = []
    with zipfile.ZipFile(archive_path) as archive:
        manifest = next(name for name in archive.namelist() if name.endswith("classification_manifest.csv"))
        rows = csv.DictReader(io.TextIOWrapper(archive.open(manifest), encoding="utf-8-sig"))
        for row in rows:
            if row["Status"] != "copied_jpg" or row["JpgExists"] != "True":
                continue
            percent = int(row["WearPercent"])
            basename = f"{row['BaseName']}.jpg"
            member = next(name for name in archive.namelist() if name.endswith(f"/{percent}%/{basename}"))
            destination = staging / basename
            with archive.open(member) as source, destination.open("wb") as output:
                shutil.copyfileobj(source, output)
            records.append({
                "id": f"WEAR-{percent:03d}-{row['BaseName']}",
                "image": f"data/wear_percent_cases/{basename}",
                "wear_rate": percent / 100,
                "wear_percent": percent,
                "source": "使用者提供磨耗%資料集",
            })

    if len(records) < 5:
        shutil.rmtree(staging)
        raise RuntimeError("有效標註圖片少於 5 張，未取代舊資料。")

    if target.exists():
        shutil.rmtree(target)
    staging.rename(target)
    (DATA / "cases.json").write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Imported {len(records)} wear-percent cases.")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
