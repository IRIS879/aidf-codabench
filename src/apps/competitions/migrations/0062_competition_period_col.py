from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('competitions', '0061_competition_training_mode'),
    ]

    operations = [
        migrations.AddField(
            model_name='competition',
            name='period_col',
            field=models.CharField(blank=True, max_length=128, null=True),
        ),
    ]
