import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def delete_orphan_progress(apps, schema_editor):
    """Remove o progresso global existente: sem usuário, é órfão e não pode ser atribuído.
    O progresso passa a ser criado sob demanda por usuário."""
    ReadingProgress = apps.get_model('reader', 'ReadingProgress')
    ReadingProgress.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('reader', '0003_post_featured'),
    ]

    operations = [
        # 1. Limpa os registros órfãos antes de mudar o schema
        migrations.RunPython(delete_orphan_progress, migrations.RunPython.noop),
        # 2. post deixa de ser OneToOne e vira ForeignKey (vários usuários por post)
        migrations.AlterField(
            model_name='readingprogress',
            name='post',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='progress',
                to='reader.post',
            ),
        ),
        # 3. Adiciona o dono do progresso
        migrations.AddField(
            model_name='readingprogress',
            name='user',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='reading_progress',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        # 4. Um progresso por (usuário, post)
        migrations.AlterUniqueTogether(
            name='readingprogress',
            unique_together={('user', 'post')},
        ),
    ]
