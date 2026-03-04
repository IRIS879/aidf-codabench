from django.db import migrations, models


def copy_date_bounds_to_period(apps, schema_editor):
    Competition = apps.get_model('competitions', 'Competition')
    for comp in Competition.objects.filter(training_mode='rolling'):
        changed = False
        if not comp.rolling_start_period and comp.rolling_window_start_date:
            comp.rolling_start_period = comp.rolling_window_start_date.isoformat()
            changed = True
        if not comp.rolling_end_period and comp.rolling_window_end_date:
            comp.rolling_end_period = comp.rolling_window_end_date.isoformat()
            changed = True
        if changed:
            comp.save(update_fields=['rolling_start_period', 'rolling_end_period'])


class Migration(migrations.Migration):

    dependencies = [
        ('competitions', '0062_competition_period_col'),
    ]

    operations = [
        migrations.AddField(
            model_name='competition',
            name='rolling_end_period',
            field=models.CharField(blank=True, max_length=128, null=True),
        ),
        migrations.AddField(
            model_name='competition',
            name='rolling_start_period',
            field=models.CharField(blank=True, max_length=128, null=True),
        ),
        migrations.RunPython(copy_date_bounds_to_period, migrations.RunPython.noop),
    ]
