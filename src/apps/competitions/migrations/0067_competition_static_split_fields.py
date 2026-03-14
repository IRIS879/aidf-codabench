from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("competitions", "0066_drop_legacy_phase_rolling_columns"),
    ]

    operations = [
        migrations.AddField(
            model_name="competition",
            name="static_split_column",
            field=models.CharField(blank=True, max_length=128, null=True),
        ),
        migrations.AddField(
            model_name="competition",
            name="static_split_value",
            field=models.CharField(blank=True, max_length=128, null=True),
        ),
    ]
