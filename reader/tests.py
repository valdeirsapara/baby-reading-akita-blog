from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from unittest.mock import patch
from io import StringIO
import json

from .models import Post, ReadingProgress, YouTubeVideo

User = get_user_model()

class ReaderModelsTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="leitor", password="x")
        self.post = Post.objects.create(
            title="Como Começar a Programar em 2026",
            url="https://www.akitaonrails.com/posts/como-comecar-a-programar-em-2026",
            published_at=timezone.now(),
            summary="Um guia básico.",
            content="<p>Conteúdo completo do post</p>"
        )

    def test_post_slug_generation_on_save(self):
        """Testa se o slug do post é gerado automaticamente a partir da URL original."""
        self.assertEqual(self.post.slug, "como-comecar-a-programar-em-2026")

    def test_reading_progress_creation_defaults(self):
        """Testa se o progresso de leitura padrão é criado com valores corretos."""
        progress, created = ReadingProgress.objects.get_or_create(post=self.post, user=self.user)
        self.assertEqual(progress.status, "unread")
        self.assertEqual(progress.scroll_position, 0.0)

    def test_reading_progress_scoped_per_user(self):
        """Cada usuário tem seu próprio progresso para o mesmo post."""
        other = User.objects.create_user(username="outro", password="x")
        p1, _ = ReadingProgress.objects.get_or_create(post=self.post, user=self.user)
        p1.status = "read"
        p1.save()
        p2, _ = ReadingProgress.objects.get_or_create(post=self.post, user=other)
        self.assertEqual(p2.status, "unread")
        self.assertNotEqual(p1.pk, p2.pk)

class ReaderViewsTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="leitor", password="x")
        self.client = Client()
        self.client.force_login(self.user)
        self.post = Post.objects.create(
            title="Artigo de Teste",
            url="https://www.akitaonrails.com/posts/artigo-de-teste",
            published_at=timezone.now(),
            summary="Resumo de teste",
            content="Corpo de teste"
        )
        self.progress = ReadingProgress.objects.create(
            user=self.user,
            post=self.post,
            status="unread",
            scroll_position=0.0
        )

    def test_requires_login(self):
        """Sem login, as páginas do leitor redirecionam para o login."""
        anon = Client()
        resp = anon.get(reverse('reader:posts_list'))
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/auth/login/', resp.headers.get('Location', ''))

    def test_dashboard_status(self):
        """Testa se a página inicial do leitor carrega com sucesso."""
        resp = self.client.get(reverse('reader:dashboard'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'DashboardController')

    def test_posts_list_json_api(self):
        """Testa se a API de listagem de posts retorna o JSON com o progresso correspondente."""
        resp = self.client.get(reverse('reader:posts_list'))
        self.assertEqual(resp.status_code, 200)
        
        data = json.loads(resp.content)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['title'], "Artigo de Teste")
        self.assertEqual(data[0]['status'], "unread")
        self.assertEqual(data[0]['scroll_position'], 0.0)

    def test_update_progress_api(self):
        """Testa se a API de atualização de progresso salva o status e scroll corretamente."""
        url = reverse('reader:update_progress')
        payload = {
            'post_id': self.post.id,
            'status': 'reading',
            'scroll_position': 45.5
        }
        resp = self.client.post(
            url, 
            data=json.dumps(payload), 
            content_type='application/json',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(resp.status_code, 200)
        
        # Recarrega do banco de dados
        self.progress.refresh_from_db()
        self.assertEqual(self.progress.status, "reading")
        self.assertEqual(self.progress.scroll_position, 45.5)

    @patch('requests.get')
    def test_sync_feed_api(self, mock_get):
        """Testa a sincronização mockada do RSS feed do Akita."""
        # Mock do retorno do request com feed RSS XML simplificado
        mock_xml = """<?xml version="1.0" encoding="utf-8" standalone="yes"?>
        <rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
          <channel>
            <title>AkitaOnRails</title>
            <link>https://www.akitaonrails.com/</link>
            <item>
              <title>Novo Post do Akita</title>
              <link>https://www.akitaonrails.com/posts/novo-post-akita</link>
              <pubDate>Mon, 13 Jul 2026 12:00:00 -0400</pubDate>
              <description>Descrição curta do novo post.</description>
            </item>
          </channel>
        </rss>
        """
        mock_get.return_value.status_code = 200
        mock_get.return_value.content = mock_xml.encode('utf-8')

        # Aciona sincronização
        resp = self.client.post(
            reverse('reader:sync_feed'),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(resp.status_code, 200)
        
        data = json.loads(resp.content)
        self.assertTrue(data['success'])
        self.assertEqual(data['new_posts_count'], 1)
        
        # Verifica se o post foi salvo no banco de dados
        self.assertTrue(Post.objects.filter(url="https://www.akitaonrails.com/posts/novo-post-akita").exists())
        new_post = Post.objects.get(url="https://www.akitaonrails.com/posts/novo-post-akita")
        self.assertEqual(new_post.title, "Novo Post do Akita")
        self.assertEqual(new_post.slug, "novo-post-akita")
        # O progresso é criado sob demanda por usuário — não na importação
        self.assertEqual(new_post.progress.count(), 0)


class YouTubeIntegrationTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.post = Post.objects.create(
            title="Post com Vídeo",
            url="https://www.akitaonrails.com/posts/post-com-video",
            published_at=timezone.now(),
            summary="Post com vídeo",
            content='<p>Assista ao vídeo:</p><div class="embed-container">  </div>'
        )

    def test_youtube_video_model(self):
        video = YouTubeVideo.objects.create(
            post=self.post,
            youtube_id="dQw4w9WgXcQ",
            title="Never Gonna Give You Up",
            thumbnail_url="https://img.youtube.com/vi/dQw4w9WgXcQ/hqdefault.jpg",
            url="https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        )
        self.assertEqual(video.youtube_id, "dQw4w9WgXcQ")
        self.assertEqual(str(video), "Never Gonna Give You Up (Post com Vídeo)")

    @patch('requests.get')
    def test_extract_and_update_youtube_videos(self, mock_get):
        # Mock responses
        # 1. Scraping the live page (returns HTML containing the iframe)
        mock_live_html = '<html><body><article><iframe src="https://www.youtube.com/embed/dQw4w9WgXcQ"></iframe></article></body></html>'
        
        # 2. YouTube oEmbed metadata API call
        mock_oembed_json = {
            'title': 'Rick Astley - Never Gonna Give You Up',
            'thumbnail_url': 'https://i.ytimg.com/vi/dQw4w9WgXcQ/hqdefault.jpg'
        }
        
        class MockResponse:
            def __init__(self, text, status_code, json_data=None):
                self.text = text
                self.status_code = status_code
                self.json_data = json_data
            
            def json(self):
                return self.json_data
                
        # Side effect to handle both URL requests:
        # First request: post.url -> returns live html
        # Second request: oembed -> returns oembed json
        def get_side_effect(url, *args, **kwargs):
            if "oembed" in url:
                return MockResponse("", 200, mock_oembed_json)
            else:
                return MockResponse(mock_live_html, 200)
                
        mock_get.side_effect = get_side_effect
        
        from reader.utils import extract_and_update_youtube_videos
        success = extract_and_update_youtube_videos(self.post)
        self.assertTrue(success)
        
        # Verify the HTML got healed
        self.post.refresh_from_db()
        self.assertIn('src="https://www.youtube.com/embed/dQw4w9WgXcQ"', self.post.content)
        
        # Verify YouTubeVideo object was created
        self.assertEqual(YouTubeVideo.objects.count(), 1)
        video = YouTubeVideo.objects.first()
        self.assertEqual(video.youtube_id, "dQw4w9WgXcQ")
        self.assertEqual(video.title, "Rick Astley - Never Gonna Give You Up")


class ImportAkitaPostsCommandTestCase(TestCase):
    @patch("reader.management.commands.import_akita_posts.import_archive")
    def test_command_imports_complete_archive(self, mock_import_archive):
        mock_import_archive.return_value = 42
        stdout = StringIO()

        call_command("import_akita_posts", stdout=stdout)

        mock_import_archive.assert_called_once()
        options = mock_import_archive.call_args.kwargs
        self.assertEqual(options["limit"], 0)
        self.assertEqual(options["delay"], 0.5)
        self.assertFalse(options["skip_content"])
        self.assertTrue(options["extract_videos"])
        self.assertIn("42 novo(s) post(s)", stdout.getvalue())

    @patch("reader.management.commands.import_akita_posts.import_archive")
    def test_command_forwards_options(self, mock_import_archive):
        mock_import_archive.return_value = 3

        call_command(
            "import_akita_posts",
            limit=3,
            delay=0,
            skip_content=True,
            skip_videos=True,
            stdout=StringIO(),
        )

        options = mock_import_archive.call_args.kwargs
        self.assertEqual(options["limit"], 3)
        self.assertEqual(options["delay"], 0)
        self.assertTrue(options["skip_content"])
        self.assertFalse(options["extract_videos"])

    def test_command_rejects_negative_values(self):
        with self.assertRaises(CommandError):
            call_command("import_akita_posts", limit=-1, stdout=StringIO())


