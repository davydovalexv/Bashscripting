from pathlib import Path

from dv_agent.parser.loader import parse_sql_path
from dv_agent.parser.options import ParseOptions
from dv_agent.ui.services import parse_result_to_dataframe, save_uploaded_files, uploads_dir


def test_parse_result_to_dataframe(tmp_path, monkeypatch):
  sql = tmp_path / "t.sql"
  sql.write_text(
      "CREATE TABLE demo (id INT PRIMARY KEY, name VARCHAR(50));",
      encoding="utf-8",
  )
  parsed = parse_sql_path(sql, ParseOptions())
  df = parse_result_to_dataframe(parsed)
  assert len(df) == 1
  assert df.iloc[0]["table"] == "demo"
  assert df.iloc[0]["columns"] == 2


def test_save_uploaded_files(tmp_path, monkeypatch):
  from dv_agent.config import load_config

  cfg = load_config()
  monkeypatch.setattr(
      "dv_agent.ui.services.uploads_dir",
      lambda _cfg=None: tmp_path / "workspace",
  )

  class FakeUpload:
    name = "sample.sql"

    def getbuffer(self):
      return b"CREATE TABLE x (a INT);"

  saved = save_uploaded_files([FakeUpload()], cfg)
  assert len(saved) == 1
  assert saved[0].read_text(encoding="utf-8").startswith("CREATE TABLE")
