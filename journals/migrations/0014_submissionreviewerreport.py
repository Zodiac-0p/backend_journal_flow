from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('journals', '0013_submissionreviewerassignment_reviewer_response_reminder_sent_at'),
    ]

    operations = [
        migrations.CreateModel(
            name='SubmissionReviewerReport',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('review_report_complete', models.BooleanField(default=False)),
                ('ready_to_transfer_to_editor', models.BooleanField(default=False)),
                ('recommendation', models.CharField(blank=True, choices=[('accept', 'Accept'), ('reject', 'Reject'), ('minor_revision', 'Minor Revision'), ('major_revision', 'Major Revision')], max_length=20)),
                ('reviewer_comments_to_author', models.TextField(blank=True)),
                ('confidential_comments_to_editor', models.TextField(blank=True)),
                ('paper_referee_confidence', models.CharField(blank=True, choices=[('confident', 'With confidence'), ('not_able', 'I am not able to referee this mss')], max_length=20)),
                ('referee_suitability_rating', models.CharField(blank=True, choices=[('100', '100%'), ('75', '75%'), ('50', '50%'), ('25', '25%'), ('0', '0%')], max_length=3)),
                ('paper_quality_rating', models.CharField(blank=True, choices=[('excellent', 'Excellent'), ('significant', 'Significant'), ('marginal', 'Marginal'), ('non_significant', 'Non Significant'), ('erroneous_or_trivial', 'Erroneous or Trivial')], max_length=30)),
                ('paper_value_rating', models.CharField(blank=True, choices=[('worth_publishing', 'Worth publishing'), ('minor_modifications', 'Worth publishing when revised - minor modifications'), ('major_modifications', 'Worth publishing when revised - major modifications'), ('not_worth_publishing', 'Not worth publishing')], max_length=30)),
                ('suitable_for_different_journal', models.BooleanField(blank=True, null=True)),
                ('content_original_work', models.BooleanField(blank=True, null=True)),
                ('content_well_organised', models.BooleanField(blank=True, null=True)),
                ('content_abstract_adequate', models.BooleanField(blank=True, null=True)),
                ('content_technically_sound', models.BooleanField(blank=True, null=True)),
                ('content_practical_application', models.BooleanField(blank=True, null=True)),
                ('content_references_adequate', models.BooleanField(blank=True, null=True)),
                ('presentation_explains_clearly', models.BooleanField(blank=True, null=True)),
                ('presentation_methods_included', models.BooleanField(blank=True, null=True)),
                ('presentation_demonstrates_value', models.BooleanField(blank=True, null=True)),
                ('presentation_language_clear', models.BooleanField(blank=True, null=True)),
                ('manuscript_classification', models.CharField(blank=True, choices=[('review', 'A review'), ('paper', 'A paper'), ('communication', 'A communication'), ('technical_note', 'A technical note')], max_length=20)),
                ('submitted_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('assignment', models.OneToOneField(on_delete=models.CASCADE, related_name='review_report', to='journals.submissionreviewerassignment')),
            ],
            options={
                'ordering': ['-updated_at'],
            },
        ),
    ]
