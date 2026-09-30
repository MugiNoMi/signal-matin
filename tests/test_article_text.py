from signal_matin.connectors.article_text import extract_article_text

PAGE = """<html><body>
<nav><p>Accueil — Rubriques — Se connecter pour lire la suite de nos articles</p></nav>
<article>
  <h1>Titre</h1>
  <p>Premier paragraphe de l'article, suffisamment long pour être gardé par l'extracteur.</p>
  <figure><figcaption><p>Légende de photo assez longue mais qui ne fait pas partie du texte.</p></figcaption></figure>
  <p>Court.</p>
  <p>Deuxième paragraphe de l'article, lui aussi assez long pour franchir le seuil minimal.</p>
  <script>var p = "<p>faux paragraphe injecté par un script, très long, à ignorer</p>";</script>
</article>
<footer><p>Mentions légales et conditions générales d'utilisation du site d'information.</p></footer>
</body></html>"""


def test_extract_article_text_keeps_body_paragraphs_only():
    text = extract_article_text(PAGE, min_paragraph=40)
    assert text.split("\n\n") == [
        "Premier paragraphe de l'article, suffisamment long pour être gardé par l'extracteur.",
        "Deuxième paragraphe de l'article, lui aussi assez long pour franchir le seuil minimal.",
    ]


def test_extract_article_text_falls_back_to_the_whole_page_and_caps_length():
    page = "<div>" + "<p>" + "Un paragraphe hors balise article, assez long. " * 3 + "</p>" * 1 + "</div>"
    assert extract_article_text(page).startswith("Un paragraphe hors balise article")
    long_page = "<article>" + "".join(f"<p>{'Mot ' * 50}{i}</p>" for i in range(200)) + "</article>"
    assert len(extract_article_text(long_page, max_chars=1000)) == 1000
