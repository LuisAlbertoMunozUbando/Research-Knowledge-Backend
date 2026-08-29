import argparse
import json
from pathlib import Path

from app.packages import create_package
from app.add_slide import add_slide
from app.synthesize_package import get_package_with_slides, synthesize, save_synthesis
from app.canonicalize_package import canonicalize, save_final


def copy_verified_into_processed(src: Path) -> Path:
    src = src.expanduser().resolve()
    if not src.exists():
        raise FileNotFoundError(src)
    return src


def run_pipeline(title, verified_files, user_note=""):
    print()
    print("=== IMAGE2TODOLIST PACKAGE PIPELINE ===")
    print()

    package_id = create_package(
        title=title,
        expected_slides=len(verified_files),
        user_note=user_note,
    )

    print("PACKAGE CREATED")
    print("ID:", package_id)
    print("TITLE:", title)
    print("EXPECTED SLIDES:", len(verified_files))
    print()

    for index, verified_file in enumerate(verified_files, start=1):
        path = copy_verified_into_processed(Path(verified_file))
        print(f"Adding slide {index}/{len(verified_files)}:")
        print(path)
        result = add_slide(
            package_id=package_id,
            sequence=index,
            verified_path=path,
        )
        print(json.dumps(result, indent=2, ensure_ascii=False))
        print()

    package, slides = get_package_with_slides(package_id)

    print("SYNTHESIZING PACKAGE WITH NEMOTRON...")
    print()
    synthesis = synthesize(package, slides)
    save_synthesis(package_id, synthesis)

    print("SYNTHESIS:")
    print(json.dumps(synthesis, indent=2, ensure_ascii=False))
    print()

    print("CANONICALIZING...")
    print()
    final = canonicalize(synthesis)
    save_final(package_id, final)

    print("PACKAGE FINAL:")
    print(json.dumps(final, indent=2, ensure_ascii=False))
    print()
    print("=== PIPELINE COMPLETE ===")
    print()
    print("PACKAGE ID:", package_id)
    return package_id


def main():
    parser = argparse.ArgumentParser(
        description="Image2ToDoList package pipeline for verified visual JSON files."
    )
    parser.add_argument("--title", required=True, help="Short package title")
    parser.add_argument(
        "--slides",
        nargs="+",
        required=True,
        help="Verified slide JSON files",
    )
    parser.add_argument("--note", default="", help="Optional original user note")
    args = parser.parse_args()
    run_pipeline(
        title=args.title,
        verified_files=args.slides,
        user_note=args.note,
    )


if __name__ == "__main__":
    main()
