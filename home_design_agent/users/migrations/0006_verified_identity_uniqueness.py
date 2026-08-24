import re

from django.db import migrations, models
from django.db.models import Q


def backfill_verified_identities(apps, schema_editor):
    UserProfile = apps.get_model('users', 'UserProfile')
    seen_phones = set()
    seen_emails = set()
    for profile in UserProfile.objects.select_related('user').order_by('id').iterator():
        update_fields = []
        phone = re.sub(r'[\s\-()]', '', profile.phone or '')
        if phone:
            if phone in seen_phones:
                profile.phone = ''
                update_fields.append('phone')
            else:
                seen_phones.add(phone)
                if profile.phone != phone:
                    profile.phone = phone
                    update_fields.append('phone')

        email = (profile.user.email or '').strip().lower() if profile.email_verified else ''
        if email and email not in seen_emails:
            seen_emails.add(email)
            profile.verified_email = email
            update_fields.append('verified_email')
        elif email:
            profile.email_verified = False
            profile.verified_email = ''
            update_fields.extend(['email_verified', 'verified_email'])

        if update_fields:
            profile.save(update_fields=update_fields)


def clear_verified_identities(apps, schema_editor):
    UserProfile = apps.get_model('users', 'UserProfile')
    UserProfile.objects.update(verified_email='')


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0005_remembertoken'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='verified_email',
            field=models.EmailField(
                blank=True,
                help_text='仅在验证码校验成功后写入，用于唯一登录身份匹配。',
                max_length=254,
                verbose_name='已验证邮箱标识',
            ),
        ),
        migrations.RunPython(backfill_verified_identities, clear_verified_identities),
        migrations.AddConstraint(
            model_name='userprofile',
            constraint=models.UniqueConstraint(
                condition=~Q(phone=''), fields=('phone',), name='users_unique_bound_phone',
            ),
        ),
        migrations.AddConstraint(
            model_name='userprofile',
            constraint=models.UniqueConstraint(
                condition=~Q(verified_email=''),
                fields=('verified_email',),
                name='users_unique_verified_email',
            ),
        ),
    ]
