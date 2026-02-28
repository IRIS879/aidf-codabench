from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('competitions', '0060_merge_20251212_0942'),
    ]

    operations = [
        migrations.AddField(
            model_name='competition',
            name='rolling_window_end_date',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='competition',
            name='rolling_window_size',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='competition',
            name='rolling_window_start_date',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='competition',
            name='training_mode',
            field=models.CharField(
                choices=[('static', 'Static split'), ('rolling', 'Rolling window')],
                default='static',
                max_length=16,
            ),
        ),
    ]
