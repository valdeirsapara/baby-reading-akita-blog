from django.core.management.base import BaseCommand
from reader.models import Post
from reader.utils import extract_and_update_youtube_videos

class Command(BaseCommand):
    help = "Extracts YouTube videos from already imported Akita blog posts and heals their content"

    def handle(self, *args, **options):
        posts = Post.objects.all()
        self.stdout.write(self.style.SUCCESS(f"Iniciando enriquecimento de {posts.count()} posts..."))
        
        enriched_count = 0
        for post in posts:
            self.stdout.write(f"Processando post {post.id}: {post.title}...")
            success = extract_and_update_youtube_videos(post)
            if success:
                self.stdout.write(self.style.SUCCESS(f"  -> VÍDEOS ENCONTRADOS E ATUALIZADOS para o post {post.id}!"))
                enriched_count += 1
            else:
                self.stdout.write(self.style.WARNING(f"  -> Nenhum vídeo encontrado ou erro no post {post.id}."))
                
        self.stdout.write(self.style.SUCCESS(f"Concluído! {enriched_count} posts foram enriquecidos com vídeos do YouTube."))
