from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("competitions", "0068_competition_runtime_limit_seconds"),
    ]

    operations = [
        migrations.AddField(
            model_name="competition",
            name="model_card_submission_mode",
            field=models.CharField(
                choices=[
                    ("form", "Fill form only"),
                    ("file", "Upload file only"),
                    ("both", "Form or file"),
                ],
                default="both",
                max_length=16,
            ),
        ),
    ]
