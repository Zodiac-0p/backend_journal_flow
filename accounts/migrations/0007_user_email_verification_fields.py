from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0006_user_classifications'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='email_verification_otp',
            field=models.CharField(
                blank=True,
                max_length=128,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='user',
            name='email_verification_otp_created_at',
            field=models.DateTimeField(
                blank=True,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='user',
            name='is_email_verified',
            field=models.BooleanField(default=False),
        ),
    ]
