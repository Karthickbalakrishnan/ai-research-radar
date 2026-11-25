import argparse
import os
from pathlib import Path
from typing import Optional

import pandas as pd
from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, Field

# Load environment variables from .env before creating the OpenAI client
load_dotenv()


class CleanedStudent(BaseModel):
    Student_ID: str = Field(..., description="Uppercase ID like STU1050")
    Name: str = Field(..., description="Trimmed full name with single spaces")
    Email: Optional[str] = Field(
        None, description="Lowercased email, or null if blank/invalid"
    )
    Email_Valid: bool = Field(
        ..., description="True only if Email is a valid standard email address"
    )
    Phone: Optional[str] = Field(
        None, description="Digits-only phone number (strip leading 91 if 12 digits)"
    )
    Course: str = Field(..., description="Cleaned course name")
    Fee_Paid: bool = Field(
        ..., description="True if fee is paid/completed, False if unpaid/pending/due"
    )
    City: str = Field(..., description="Cleaned city name")
    Enrolled_Date: Optional[str] = Field(
        None, description="Date in YYYY-MM-DD format if valid, else null"
    )


class CleanedStudentBatch(BaseModel):
    students: list[CleanedStudent]


def get_openai_client() -> OpenAI:
    """Initialize OpenAI client using OPENAI_API_KEY from .env or environment."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not found. Add it to your .env file.")
    return OpenAI(api_key=api_key)


def step_1_upload_csv(
    file_path: str | None = None, output_path: str = "students_cleaned.csv"
) -> Path:
    """Step 1: Resolve CLI path, auto-detect a single CSV in the folder, or prompt."""
    output_resolved = Path(output_path).resolve()

    if not file_path:
        # Look for non-output CSV files in the current working directory
        candidate_csvs = [
            p
            for p in Path(".").iterdir()
            if p.is_file()
            and p.suffix.lower() == ".csv"
            and p.resolve() != output_resolved
            and not p.name.endswith("_cleaned.csv")
        ]

        if len(candidate_csvs) == 1:
            selected = candidate_csvs[0]
            print(f"[Step 1] Auto-detected single CSV file: {selected.resolve()}")
            return selected

        if len(candidate_csvs) > 1:
            names = ", ".join(p.name for p in candidate_csvs)
            print(f"[Step 1] Multiple CSV files found: {names}")

        file_path = input("Enter path to raw students CSV: ").strip().strip("'\"")

    path = Path(file_path)
    if not path.exists() or path.suffix.lower() != ".csv":
        raise FileNotFoundError(f"Valid CSV file not found at: {path}")

    print(f"[Step 1] CSV ready: {path.resolve()}")
    return path


def step_2_read_file(csv_path: Path) -> list[dict]:
    """Step 2: Read CSV and convert rows into dictionaries."""
    df = pd.read_csv(csv_path, dtype=str, keep_default_na=False)
    records = df.to_dict(orient="records")
    print(f"[Step 2] Loaded {len(records)} raw student records.")
    return records


def step_3_clean_with_openai(
    records: list[dict], batch_size: int = 25, model: str = "gpt-4o-mini"
) -> list[dict]:
    """Step 3: Clean messy student records in batches using OpenAI Structured Outputs."""
    client = get_openai_client()
    cleaned_rows: list[dict] = []

    system_prompt = (
        "You are a strict data-cleaning ETL assistant for student enrollment records. "
        "Clean each record accurately:\n"
        "- Trim extra whitespace and fix awkward capitalization in Name, Course, and City.\n"
        "- Lowercase Email. Set Email_Valid=true only if it has a valid user@domain.tld format; "
        "otherwise set Email_Valid=false and Email=null if completely unusable.\n"
        "- Extract digits for Phone (if 12 digits starting with 91, remove the 91 prefix).\n"
        "- Interpret Fee_Paid carefully: values like true, yes, paid, completed, settled -> true; "
        "false, no, unpaid, pending, due, not paid -> false.\n"
        "- Format Enrolled_Date as YYYY-MM-DD when possible, or null if invalid/missing."
    )

    for i in range(0, len(records), batch_size):
        chunk = records[i : i + batch_size]
        response = client.responses.parse(
            model=model,
            input=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Clean these student records:\n{chunk}"},
            ],
            text_format=CleanedStudentBatch,
        )
        batch_result = response.output_parsed
        if batch_result:
            cleaned_rows.extend([item.model_dump() for item in batch_result.students])
            print(
                f"[Step 3] Cleaned batch {i // batch_size + 1} "
                f"({len(batch_result.students)} rows)."
            )

    return cleaned_rows


def step_4_export_cleaned_csv(
    cleaned_records: list[dict], output_path: str = "students_cleaned.csv"
) -> Path:
    """Step 4: Deduplicate and save cleaned records to a final CSV."""
    df_clean = pd.DataFrame(cleaned_records)
    if not df_clean.empty and "Student_ID" in df_clean.columns:
        df_clean = df_clean.drop_duplicates(subset=["Student_ID"], keep="first")

    out = Path(output_path)
    df_clean.to_csv(out, index=False)
    print(f"[Step 4] Saved {len(df_clean)} cleaned records to {out.resolve()}")
    return out


def run_etl(
    input_csv: str | None = None, output_csv: str = "students_cleaned.csv"
) -> Path:
    """Run all 4 ETL steps end-to-end."""
    csv_path = step_1_upload_csv(input_csv, output_csv)
    raw_records = step_2_read_file(csv_path)
    cleaned_records = step_3_clean_with_openai(raw_records)
    return step_4_export_cleaned_csv(cleaned_records, output_csv)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Clean student CSV records using OpenAI Structured Outputs."
    )
    parser.add_argument(
        "input_csv",
        nargs="?",
        default=None,
        help="Path to raw input CSV (optional if a single CSV exists in the folder).",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="students_cleaned.csv",
        help="Path for the cleaned output CSV (default: students_cleaned.csv).",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run_etl(args.input_csv, args.output)