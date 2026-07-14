"""Importa todos os posts do arquivo completo do AkitaOnRails.

Lógica compartilhada, usada pela ação do Django admin.
"""
import re
import time
from datetime import datetime
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from django.db import transaction
from django.utils import timezone

from .models import Post, ReadingProgress
from .utils import extract_and_update_youtube_videos

ARCHIVE_URL = "https://akitaonrails.com/archives/"
BASE_URL = "https://akitaonrails.com"
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}
# Casa URLs de posts do Akita: /YYYY/MM/DD/slug/
POST_RE = re.compile(r'^/(\d{4})/(\d{2})/(\d{2})/')


def _log(logger, message):
    if logger:
        logger(message)


def fetch_archive_entries():
    """Retorna a lista de posts do arquivo: [{url, title, published_at}]."""
    resp = requests.get(ARCHIVE_URL, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.content, 'html.parser')

    entries = []
    seen = set()
    for a in soup.find_all('a', href=True):
        href = a['href']
        m = POST_RE.match(href)
        if not m or href in seen:
            continue
        seen.add(href)
        title = a.get_text(strip=True)
        if not title:
            continue
        year, month, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
        published_at = timezone.make_aware(datetime(year, month, day, 12, 0))
        entries.append({
            'url': urljoin(BASE_URL, href),
            'title': title,
            'published_at': published_at,
        })
    return entries


def fetch_post_content(url, logger=None):
    """Busca a página do post e extrai o HTML do corpo (div.content) e um resumo em texto."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        _log(logger, f"  Falha ao buscar {url}: {e}")
        return "", ""

    soup = BeautifulSoup(resp.content, 'html.parser')
    body = soup.find('div', class_='content')
    if not body:
        return "", ""

    # Torna URLs relativas (imagens e links) absolutas
    for img in body.find_all('img', src=True):
        img['src'] = urljoin(BASE_URL, img['src'])
    for a in body.find_all('a', href=True):
        a['href'] = urljoin(BASE_URL, a['href'])

    content = str(body)
    text = body.get_text(' ', strip=True)
    summary = text[:300] + ('...' if len(text) > 300 else '')
    return content, summary


def import_archive(limit=0, delay=0.5, skip_content=False, extract_videos=True, logger=None):
    """Importa os posts do arquivo completo. Retorna o número de novos posts criados."""
    _log(logger, "Buscando a página de arquivo completo...")
    entries = fetch_archive_entries()
    _log(logger, f"{len(entries)} posts encontrados no arquivo.")

    created = 0
    new_posts = []
    for entry in entries:
        if Post.objects.filter(url=entry['url']).exists():
            continue
        if limit and created >= limit:
            break

        content, summary = "", ""
        if not skip_content:
            content, summary = fetch_post_content(entry['url'], logger)
            time.sleep(delay)

        try:
            with transaction.atomic():
                post = Post.objects.create(
                    title=entry['title'],
                    url=entry['url'],
                    published_at=entry['published_at'],
                    summary=summary,
                    content=content,
                )
                ReadingProgress.objects.create(post=post, status='unread', scroll_position=0.0)
        except Exception as e:
            _log(logger, f"  Erro ao criar '{entry['title']}': {e}")
            continue

        created += 1
        new_posts.append(post)
        _log(logger, f"  [{created}] {post.title}")

    if extract_videos and not skip_content:
        _log(logger, "Extraindo vídeos do YouTube dos novos posts...")
        for post in new_posts:
            try:
                extract_and_update_youtube_videos(post)
                time.sleep(delay)
            except Exception as e:
                _log(logger, f"  Erro nos vídeos de {post.id}: {e}")

    _log(logger, f"Concluído! {created} novos posts importados.")
    return created
