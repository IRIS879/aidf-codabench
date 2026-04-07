from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("competitions", "0067_competition_static_split_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="competition",
            name="runtime_limit_seconds",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
    ]

