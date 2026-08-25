from django.db import migrations, models


def create_default_config(apps, schema_editor):
    VerificationConfig = apps.get_model('users', 'VerificationConfig')
    VerificationConfig.objects.get_or_create(name='default')


def remove_default_config(apps, schema_editor):
    VerificationConfig = apps.get_model('users', 'VerificationConfig')
    VerificationConfig.objects.filter(name='default').delete()


class Migration(migrations.Migration):
    dependencies = [
        ('users', '0006_verified_identity_uniqueness'),
    ]

    operations = [
        migrations.CreateModel(
            name='VerificationConfig',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(default='default', max_length=50, unique=True, verbose_name='配置名')),
                ('phone_verification_enabled', models.BooleanField(default=False, help_text='控制短信验证码发送、手机号绑定和手机号验证码登录接口及前端入口。', verbose_name='启用手机号验证功能')),
                ('email_verification_enabled', models.BooleanField(default=False, help_text='控制邮箱验证码发送、邮箱验证和邮箱验证码登录接口及前端入口。', verbose_name='启用邮箱验证功能')),
                ('require_phone_verification_for_order', models.BooleanField(default=False, help_text='开启后，下单必须使用当前账号已短信验证的手机号。', verbose_name='下单必须验证手机号')),
                ('require_email_verification_for_order', models.BooleanField(default=False, help_text='开启后，下单前必须完成当前账号邮箱验证。', verbose_name='下单必须验证邮箱')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
            ],
            options={
                'verbose_name': '验证功能配置',
                'verbose_name_plural': '验证功能配置',
            },
        ),
        migrations.RunPython(create_default_config, remove_default_config),
    ]
