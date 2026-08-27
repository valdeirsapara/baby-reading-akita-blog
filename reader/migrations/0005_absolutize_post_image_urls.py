"""Corrige URLs relativas de imagens nos posts já importados.

Posts trazidos pelo feed RSS guardavam o HTML com caminhos relativos
(ex.: /images/foo.png), que quebram ao serem exibidos no nosso domínio.
Até agora só o comando `import_akita_posts` gerava URLs absolutas; esta
migração conserta o que já está salvo, sem precisar de comando manual.
"""
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from django.db import migrations

LOTE = 200


def _absolutizar(html, base_url):
    """Devolve (html_corrigido, alterou) com imagens e links absolutos."""
    if not html or ('<img' not in html and '<a' not in html):
        return html, False

    soup = BeautifulSoup(html, 'html.parser')
    alterou = False
    for img in soup.find_all('img', src=True):
        novo = urljoin(base_url, img['src'])
        if novo != img['src']:
            img['src'] = novo
            alterou = True
    for a in soup.find_all('a', href=True):
        novo = urljoin(base_url, a['href'])
        if novo != a['href']:
            a['href'] = novo
            alterou = True
    return (str(soup) if alterou else html), alterou


def absolutizar_urls(apps, schema_editor):
    Post = apps.get_model('reader', 'Post')

    pendentes = []
    queryset = Post.objects.exclude(content='').only('id', 'url', 'content')
    for post in queryset.iterator(chunk_size=LOTE):
        content, alterou = _absolutizar(post.content, post.url)
        if not alterou:
            continue
        post.content = content
        pendentes.append(post)
        if len(pendentes) >= LOTE:
            Post.objects.bulk_update(pendentes, ['content'])
            pendentes = []

    if pendentes:
        Post.objects.bulk_update(pendentes, ['content'])


class Migration(migrations.Migration):

    dependencies = [
        ('reader', '0004_scope_reading_progress_by_user'),
    ]

    operations = [
        # Sem reversão: transformar URL absoluta de volta em relativa não é desejável.
        migrations.RunPython(absolutizar_urls, migrations.RunPython.noop),
    ]
