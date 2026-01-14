from pathlib import Path
import runpy


def main() -> None:
    script_path = Path(__file__).parent / "scripts" / "run_pipeline.py"
    runpy.run_path(str(script_path), run_name="__main__")


if __name__ == "__main__":
    main()
