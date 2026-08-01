from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('journals', '0014_submissionreviewerreport'),
    ]

    operations = [
        migrations.AddField(
            model_name='submission',
            name='manuscript_reference',
            field=models.CharField(
                blank=True,
                max_length=32,
                null=True,
                unique=True,
            ),
        ),
    ]
