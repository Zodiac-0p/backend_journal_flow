from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0007_user_email_verification_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='country',
            field=models.CharField(
                blank=True,
                max_length=100,
                null=True,
            ),
        ),
    ]
