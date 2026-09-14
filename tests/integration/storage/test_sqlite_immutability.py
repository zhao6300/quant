from mmqp.adapters.sqlite.schema import SqliteSchema


def test_migration_checksum_is_checked(tmp_path):
    database = tmp_path / "control.sqlite3"
    schema = SqliteSchema(database)
    schema.apply()
    schema.apply()
    schema.verify()
