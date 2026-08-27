from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.db import transaction
import feedparser
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import time
import json

from .models import Post, ReadingProgress
from .importer import absolutize_html, fetch_post_content

def dashboard(request):
    return render(request, 'reader/dashboard.html', {'vue': 'DashboardController'})

MESES_PT = {
    1: 'Janeiro', 2: 'Fevereiro', 3: 'Março', 4: 'Abril', 5: 'Maio', 6: 'Junho',
    7: 'Julho', 8: 'Agosto', 9: 'Setembro', 10: 'Outubro', 11: 'Novembro', 12: 'Dezembro',
}

def archive(request):
    """Página de arquivo completo: todos os posts agrupados por Ano - Mês."""
    posts = Post.objects.all().order_by('-published_at')
    groups = []
    current_key = None
    for post in posts:
        key = f"{post.published_at.year} - {MESES_PT[post.published_at.month]}"
        if key != current_key:
            groups.append({
                'key': key,
                'anchor': f"{post.published_at.year}-{post.published_at.month:02d}",
                'posts': [],
            })
            current_key = key
        groups[-1]['posts'].append(post)
    return render(request, 'reader/archive.html', {
        'groups': groups,
        'total': posts.count(),
        'vue': 'ArchiveController',
    })

def post_detail(request, year, month, day, slug):
    post = get_object_or_404(Post, slug=slug)
    # Garante que o progresso exista para este usuário e post
    progress, created = ReadingProgress.objects.get_or_create(post=post, user=request.user)
    return render(request, 'reader/post_detail.html', {
        'post': post,
        'progress': progress,
        'vue': 'ReaderController'
    })

def posts_list(request):
    posts = Post.objects.all()
    # Progresso do usuário atual, indexado por post
    progress_map = {
        rp.post_id: rp
        for rp in ReadingProgress.objects.filter(user=request.user)
    }
    data = []
    for post in posts:
        progress = progress_map.get(post.id)
        status = progress.status if progress else 'unread'
        scroll_position = progress.scroll_position if progress else 0.0

        data.append({
            'id': post.id,
            'title': post.title,
            'url': post.url,
            'local_url': post.get_absolute_url(),
            'published_at': post.published_at.isoformat(),
            'summary': post.summary,
            'slug': post.slug,
            'status': status,
            'scroll_position': scroll_position,
            'featured': post.featured,
        })
    return JsonResponse(data, safe=False)

@require_POST
def update_progress(request):
    try:
        body = json.loads(request.body)
        post_id = body.get('post_id')
        status = body.get('status')
        scroll_position = body.get('scroll_position', 0.0)
        
        post = get_object_or_404(Post, id=post_id)
        progress, created = ReadingProgress.objects.get_or_create(post=post, user=request.user)
        
        if status:
            progress.status = status
        progress.scroll_position = float(scroll_position)
        progress.save()
        
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)

@require_POST
def sync_feed(request):
    feed_url = "https://www.akitaonrails.com/index.xml"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        resp = requests.get(feed_url, headers=headers, timeout=15)
        resp.raise_for_status()
        
        feed = feedparser.parse(resp.content)
        new_posts = []

        # 1ª fase: monta os dados de cada post novo. As requisições de rede ficam
        # fora da transação, para não segurar o banco aberto enquanto baixamos páginas.
        pendentes = []
        for entry in feed.entries:
            # Verifica se o post já existe pela URL
            url = entry.link
            if Post.objects.filter(url=url).exists():
                continue

            # Trata data de publicação
            published_at = timezone.now()
            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                published_at = timezone.make_aware(
                    datetime.fromtimestamp(time.mktime(entry.published_parsed))
                )
            elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                published_at = timezone.make_aware(
                    datetime.fromtimestamp(time.mktime(entry.updated_parsed))
                )

            # Conteúdo do feed, usado como resumo e como plano B
            feed_content = ""
            if hasattr(entry, 'content') and entry.content:
                feed_content = entry.content[0].value
            elif hasattr(entry, 'description') and entry.description:
                feed_content = entry.description
            elif hasattr(entry, 'summary') and entry.summary:
                feed_content = entry.summary

            # Busca a página real do post: é o que traz o conteúdo completo e,
            # principalmente, as imagens com URL absoluta. Sem isso o RSS entrega
            # caminhos relativos e as imagens quebram no nosso domínio.
            content, page_summary = fetch_post_content(url)
            if not content:
                # Se a página não respondeu, ao menos corrige as URLs do feed
                content, _ = absolutize_html(feed_content, base_url=url)

            # Limpa ou formata resumo (summary) — remove tags HTML
            summary_source = entry.summary if hasattr(entry, 'summary') and entry.summary else feed_content
            summary_text = BeautifulSoup(summary_source, 'html.parser').get_text().strip()
            summary = summary_text[:300] + ('...' if len(summary_text) > 300 else '')
            if not summary:
                summary = page_summary

            pendentes.append({
                'title': entry.title,
                'url': url,
                'published_at': published_at,
                'summary': summary,
                'content': content,
            })

        # 2ª fase: grava tudo de uma vez, já sem rede envolvida
        with transaction.atomic():
            for dados in pendentes:
                # Cria o post (o progresso é criado sob demanda, por usuário)
                new_posts.append(Post.objects.create(**dados))

        # Enriquecimento com vídeos do YouTube fora da transação
        from .utils import extract_and_update_youtube_videos
        for post in new_posts:
            try:
                extract_and_update_youtube_videos(post)
            except Exception as e:
                print(f"Erro ao extrair vídeos do post {post.id}: {e}")
                
        return JsonResponse({'success': True, 'new_posts_count': len(new_posts)})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

