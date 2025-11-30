import pandas as pd
from src.utils.schema import schema_fingerprint_from_df, detect_schema_drift


def test_schema_fingerprint_and_drift():
    df1 = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
    df2 = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
    fp1 = schema_fingerprint_from_df(df1)
    fp2 = schema_fingerprint_from_df(df2)
    assert fp1["hash"] == fp2["hash"]
    # modify df2
    df3 = pd.DataFrame({"a": [1], "c": [2]})
    fp3 = schema_fingerprint_from_df(df3)
    drift = detect_schema_drift(fp1, fp3)
    assert drift["drift"] is True
    assert "removed" in drift["diff"] and "b" in drift["diff"]["removed"]
