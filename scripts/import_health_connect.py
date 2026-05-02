from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPORT_DIR = ROOT / "data" / "health-connect-export"


def main():
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    files = sorted(
        path for path in EXPORT_DIR.iterdir()
        if path.is_file() and path.suffix.lower() in {".zip", ".csv"}
    )

    if files:
        print("Health-Connect-Dateien gefunden:")
        for path in files:
            print(f" - {path.name}")
    else:
        print(f"Keine ZIP- oder CSV-Dateien in {EXPORT_DIR} gefunden.")

    print(
        "Health-Connect-Import ist vorbereitet. Der konkrete Parser wird ergaenzt, "
        "sobald ein echter Export mit bekanntem Format vorliegt."
    )


if __name__ == "__main__":
    main()
