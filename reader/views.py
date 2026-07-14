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
    # Garante que o progresso exista para o post
    progress, created = ReadingProgress.objects.get_or_create(post=post)
    return render(request, 'reader/post_detail.html', {
        'post': post,
        'progress': progress,
        'vue': 'ReaderController'
    })

def posts_list(request):
    posts = Post.objects.all().prefetch_related('progress')
    data = []
    for post in posts:
        # Pega ou cria progresso padrão
        progress = getattr(post, 'progress', None)
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
        progress, created = ReadingProgress.objects.get_or_create(post=post)
        
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
        
        with transaction.atomic():
            for entry in feed.entries:
                # Verifica se o post já existe pela URL
                url = entry.link
                if Post.objects.filter(url=url).exists():
                    continue
                
                title = entry.title
                
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
                
                # Trata conteúdo do post
                content = ""
                if hasattr(entry, 'content') and entry.content:
                    content = entry.content[0].value
                elif hasattr(entry, 'description') and entry.description:
                    content = entry.description
                elif hasattr(entry, 'summary') and entry.summary:
                    content = entry.summary
                
                # Limpa ou formata resumo (summary) — remove tags HTML
                summary_source = entry.summary if hasattr(entry, 'summary') and entry.summary else content
                summary_text = BeautifulSoup(summary_source, 'html.parser').get_text().strip()
                summary = summary_text[:300] + ('...' if len(summary_text) > 300 else '')
                
                # Cria o post
                post = Post.objects.create(
                    title=title,
                    url=url,
                    published_at=published_at,
                    summary=summary,
                    content=content
                )
                
                # Inicializa o progresso
                ReadingProgress.objects.create(post=post, status='unread', scroll_position=0.0)
                new_posts.append(post)
        
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

