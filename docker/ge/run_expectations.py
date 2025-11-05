import json
import os
from datetime import datetime

import pandas as pd
from great_expectations.dataset import PandasDataset


def build_expectations(dataset: PandasDataset) -> None:
    columns = dataset.get_table_columns()
    pandas_dtypes = dataset.dtypes

    for column in columns:
        dataset.expect_column_values_to_not_be_null(column)
        dtype_name = str(pandas_dtypes[column])
        dataset.expect_column_values_to_be_in_type_list(column, [dtype_name])

    if "message_id" in columns:
        dataset.expect_column_values_to_be_unique("message_id")

    if "sent_at" in columns:
        dataset.expect_column_values_to_match_strftime_format("sent_at", "%Y-%m-%d %H:%M:%S")

    if "has_attachment" in columns:
        dataset.expect_column_values_to_be_in_set("has_attachment", {"true", "false", True, False})


def main() -> None:
    input_path = os.environ.get("GE_INPUT", "artifacts/data/tabular/tabular_enron.csv")
    output_path = os.environ.get("GE_OUTPUT", "reports/ge/summary.json")

    df = pd.read_csv(input_path)
    dataset = PandasDataset(df)
    build_expectations(dataset)
    result = dataset.validate(result_format="SUMMARY")

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "generated_at": datetime.utcnow().isoformat() + "Z",
                "input_path": input_path,
                "expectation_suite": result["statistics"],
                "success": result["success"],
                "meta": result.get("meta", {}),
            },
            f,
            indent=2,
        )


if __name__ == "__main__":
    main()
