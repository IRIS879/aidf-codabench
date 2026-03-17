from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("competitions", "0065_rename_model_card_json_submission_model_card_parsed_json_and_more"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                ALTER TABLE competitions_phase DROP COLUMN IF EXISTS rolling_enabled;
                ALTER TABLE competitions_phase DROP COLUMN IF EXISTS rolling_start_year;
                ALTER TABLE competitions_phase DROP COLUMN IF EXISTS rolling_end_year;
                ALTER TABLE competitions_phase DROP COLUMN IF EXISTS rolling_window_size;
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]

