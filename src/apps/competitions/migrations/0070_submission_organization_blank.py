from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("profiles", "0021_merge_0020_alter_user_quota_0020_merge_20251212_0942"),
        ("competitions", "0069_competition_model_card_submission_mode"),
    ]

    operations = [
        migrations.AlterField(
            model_name="submission",
            name="organization",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.DO_NOTHING,
                related_name="submissions",
                to="profiles.organization",
            ),
        ),
    ]
