from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("leaderboards", "0009_alter_column_id_alter_leaderboard_id_and_more"),
        ("competitions", "0070_submission_organization_blank"),
    ]

    operations = [
        migrations.AlterField(
            model_name="submission",
            name="scores",
            field=models.ManyToManyField(
                blank=True,
                related_name="submissions",
                to="leaderboards.submissionscore",
            ),
        ),
    ]
