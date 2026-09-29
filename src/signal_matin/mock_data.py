"""Edition fictive complete pour developper le design sans API ni donnees perso."""
from __future__ import annotations

import datetime as dt

from .models import (
    AgendaItem, DataSourceStatus, DataState, DensityMode, DigestItem, EditionMeta, EditorialBlock,
    Extras, Illustration, Importance, MorningEdition, NewsBundle, NewsItem,
    MacroEvent, MarketMover, MarketMovers, MarketQuote, MarketsPage,
    PersonalBlock, QuizBlock, QuoteBlock, Recommendation, SourceRef, SportEvent,
    SportPage, SportRecap, SportTable, TaskItem, WeatherBlock, WordOfTheDay,
)
from .daily_learning import construire_apprentissage_du_jour


def _source(date: dt.date, rubrique: str) -> SourceRef:
    return SourceRef(
        name="Source fictive - donnees de demonstration",
        url=f"https://example.invalid/signal-matin/{rubrique}",
        published_at=dt.datetime.combine(date, dt.time(6, 30)).astimezone(),
    )


def _news(date: dt.date, title: str, category: str, summary: str,
          importance: Importance = Importance.NORMAL,
          illustration: bool = False) -> NewsItem:
    return NewsItem(
        title=f"DEMO - {title}",
        category=category,
        summary=summary,
        source=_source(date, category.lower().replace(" ", "-")),
        importance=importance,
        illustration=(Illustration(
            type="engraving", alt="Nature morte matinale dessinee au trait",
            caption="Illustration editoriale de demonstration, sans valeur documentaire.",
        ) if illustration else None),
    )


def _sport_demo(date: dt.date, at) -> SportPage:
    tomorrow = date + dt.timedelta(days=1)
    return SportPage(
        today=[
            SportEvent(sport="basketball", competition="NBA", highlight=True,
                       label="DEMO - Equipe suivie – Adversaire (à domicile)",
                       when=f"19h30 heure locale ({tomorrow:%d/%m} à 2h30 heure de Paris)",
                       detail="Bilan 12-5"),
            SportEvent(sport="football", competition="Ligue des champions",
                       label="DEMO - Club A – Club B", when="21h00", detail="Stade fictif"),
            SportEvent(sport="tennis", competition="ATP · Tournoi de démonstration",
                       label="DEMO - Joueur A (3) – Joueur B (14)", when="13h30",
                       detail="Quart de finale", start=at(13, 30)),
            SportEvent(sport="tennis", competition="WTA · Tournoi de démonstration",
                       label="DEMO - Joueuse A (2) bat Joueuse B 6-4 6-3", when="Terminé",
                       detail="8e de finale"),
        ],
        recaps=[
            SportRecap(competition="NBA", highlight=True,
                       headline="DEMO - Equipe suivie 112 – 104 Adversaire",
                       lines=["Victoire à domicile, bilan 12-5",
                              "Equipe suivie : Joueur fictif (31 pts, 12 rbds, 5 ctres)",
                              "Adversaire : Autre joueur (27 pts, 8 pd)"]),
        ],
        tables=[SportTable(
            title="DEMO - Classement fictif", highlight="Equipe suivie",
            columns=["Rg", "Équipe", "V", "D", "%"],
            rows=[["1", "Equipe suivie", "12", "5", ".706"], ["2", "Autre equipe", "11", "6", ".647"],
                  ["3", "Troisieme equipe", "9", "8", ".529"]],
        )],
        notes=["DEMO - Equipe suivie : bilan 12-5, 1er de la division"],
    )


def _markets_demo() -> MarketsPage:
    def mover(name: str, change: float) -> MarketMover:
        return MarketMover(name=f"DEMO - {name}", symbol="DEMO", price=100.0, change_pct=change)

    return MarketsPage(
        quotes=[
            MarketQuote(name="Indice A", symbol="DEMO-A", price=8000.0, change_pct=0.42, ytd_pct=3.1),
            MarketQuote(name="EUR/USD", symbol="DEMO-FX", price=1.1, decimals=4, change_pct=-0.12),
            MarketQuote(name="Or", symbol="DEMO-OR", price=4000.0, unit="$", change_pct=0.3),
            MarketQuote(name="Crypto A", symbol="DEMO-C", price=80000.0, unit="$",
                        change_pct=-1.8, ytd_pct=-5.0, crypto=True),
        ],
        movers=[MarketMovers(
            title="Indice de démonstration",
            gainers=[mover("Valeur A", 3.2), mover("Valeur B", 1.4)],
            losers=[mover("Valeur C", -2.1), mover("Valeur D", -0.8)],
        )],
        agenda=[MacroEvent(time="14h30", country="États-Unis", title="DEMO - Inflation sur un mois",
                           impact="Fort", forecast="0.3%", previous="0.2%")],
    )


def construire_demo(date: dt.date | None = None) -> MorningEdition:
    date = date or dt.date.today()
    tz = dt.datetime.now().astimezone().tzinfo

    def at(hour: int, minute: int = 0) -> dt.datetime:
        return dt.datetime.combine(date, dt.time(hour, minute), tzinfo=tz)

    numero = max(1, (date - dt.date(2026, 1, 1)).days + 1)
    lead = _news(
        date,
        "La matinee s'organise autour d'un temps de concentration protege",
        "A retenir",
        "Cette une est fictive. Elle montre comment Signal Matin hierarchise une information majeure, son contexte et ce qu'elle change concretement pour la journee.",
        Importance.HIGH,
        illustration=True,
    ).model_copy(update={"why_it_matters": (
        "DEMO - Une phrase d'enjeu rédigée par l'IA explique ce que l'information change pour toi."
    )})
    tech_news = [
        _news(date, "Un modele local plus compact reduit la latence", "Tech", "Une architecture fictive montre comment reduire le temps de reponse sans abandonner les outils. Le cahier technique peut ainsi presenter le fait, son fonctionnement et ce qu'il change pour un usage quotidien.", Importance.HIGH),
        _news(date, "La voix devient une interface de fond", "Tech", "Trois produits imaginaires privilegient des interactions courtes, interruptibles et plus discretes. Cette histoire de demonstration sert a tester un article technique developpe."),
        _news(date, "Un standard commun relie les agents domestiques", "IA", "Le scenario fictif decrit une methode commune pour separer le raisonnement, les autorisations et l'action materielle. Aucun standard reel n'est affirme dans cette maquette."),
        _news(date, "Les petits appareils calculent davantage en local", "Tech", "Des composants fictifs executent des fonctions autrefois reservees au cloud. Le texte permet d'eprouver une page tech dense avec plusieurs niveaux de lecture."),
        _news(date, "La sobriete numerique revient dans les interfaces", "Tech", "Une tendance imaginaire met l'accent sur des affichages calmes, des donnees utiles et des actions reversibles."),
    ]
    curiosity_news = [
        _news(date, "Pourquoi les plantes s'orientent vers la lumiere", "Sciences", "Ce sujet de curiosite fictif explique comment une observation simple peut devenir une question scientifique. Le format developpe doit donner envie de poursuivre la lecture sans transformer le journal en manuel."),
        _news(date, "Ce que les cartes anciennes racontent des villes", "Culture", "Une exposition imaginaire rapproche plans, annotations et photographies. Le sujet sert a tester une curiosite culturelle plus longue et visuellement separee de la veille technique."),
        _news(date, "Le rythme influence notre perception du temps", "Sciences", "Une etude fictive illustre la maniere dont un cahier de curiosites peut articuler hypothese, contexte et prudence."),
    ]
    edition = MorningEdition(
        generated_at=dt.datetime.now().astimezone(),
        demo=True,
        edition=EditionMeta(
            date=date, number=numero, density=DensityMode.EXTENDED,
            motto="Un matin informe, sans commencer par defiler.",
        ),
        sources=[DataSourceStatus(
            name="Toutes les rubriques",
            state=DataState.SIMULATED,
            detail="Jeu de donnees fictif reserve a la validation graphique.",
            item_count=1,
        )],
        weather=WeatherBlock(
            location="Ville de demonstration", condition="Eclaircies",
            temperature_c=13, low_c=9, high_c=18, wind_kmh=11,
            summary="Matinee fraiche, eclaircies plus franches a partir de midi.",
            advice="Une veste legere suffit ; garde le parapluie replie.",
        ),
        agenda=[
            AgendaItem(title="Revue du planning", start=at(8, 30), end=at(8, 50)),
            AgendaItem(title="Bloc de travail profond", start=at(9), end=at(10, 30), note="Notifications coupees."),
            AgendaItem(title="Point projet", start=at(11), end=at(11, 30), location="Visio"),
            AgendaItem(title="Pause et marche", start=at(12, 30), end=at(13)),
            AgendaItem(title="Preparation de demain", start=at(16, 45), end=at(17, 15)),
        ],
        priorities=[
            TaskItem(title="Terminer la tache la plus structurante avant midi", importance=Importance.HIGH),
            TaskItem(title="Valider les deux decisions en attente", importance=Importance.HIGH),
            TaskItem(title="Garder trente minutes pour la preparation de demain"),
        ],
        reminders=[
            TaskItem(title="Preparer les documents du point de 11 h", due=at(10, 45)),
            TaskItem(title="Repondre au message laisse hier", due=at(15)),
            TaskItem(title="Faire une sauvegarde avant la fin de journee"),
        ],
        news=NewsBundle(
            lead=lead,
            world=[
                _news(date, "Une alliance de villes teste un reseau energetique partage", "Monde", "Dans ce scenario fictif, plusieurs villes mettent en commun leurs previsions de consommation. Le test sert ici a verifier qu'un article distingue clairement le fait, le contexte et la consequence pratique."),
                _news(date, "Des chercheurs publient un atlas ouvert des littoraux", "Monde", "Cet exemple imaginaire decrit une base cartographique partagee entre laboratoires. Le resume est volontairement assez developpe pour eprouver la lecture en colonnes sans ressembler a une simple liste de titres."),
            ],
            france=[
                _news(date, "Une experimentation simplifie les demarches locales", "France", "Une administration fictive rassemble plusieurs formulaires dans un parcours unique. La maquette montre ainsi comment resumer le changement, rappeler son perimetre et conserver une source lisible."),
                _news(date, "Les bibliotheques etendent leurs horaires du matin", "France", "Dans cette actualite de demonstration, un reseau imaginaire ouvre plus tot deux jours par semaine. Aucun evenement reel n'est associe a ce texte, utilise uniquement pour valider le rythme editorial."),
            ],
            economy=[
                _news(date, "Les petites entreprises revoient leurs usages numeriques", "Economie", "Une enquete entierement fictive suggere que les petites structures reduisent le nombre d'outils redondants. Ce contenu mesure la densite de la page et la lisibilite des resumes economiques."),
                _news(date, "Un atelier partage mutualise ses outils", "Economie", "Le cas imaginaire suit plusieurs artisans regroupant des machines rarement utilisees. L'objectif editorial est de donner une idee concrete, son interet possible et une limite, sans surcharger la lecture."),
            ],
            society=[
                _news(date, "Le calme matinal devient un sujet de recherche", "Societe", "Des chercheurs imaginaires comparent plusieurs routines avant la premiere notification. Cet exemple, explicitement fictif, teste une rubrique societe centree sur l'attention et ses usages quotidiens."),
                _news(date, "Des voisins experimentent une bibliotheque d'objets", "Societe", "Une initiative fictive permet d'emprunter les outils qui servent peu souvent. Le texte apporte assez de matiere pour tester une page d'actualites riche tout en restant rapidement parcourable."),
            ],
            science=[
                _news(date, "Un capteur souple mesure la qualite de l'air interieur", "Sciences", "Ce prototype fictif combine plusieurs mesures dans une membrane discrete. Il n'existe pas : il sert a verifier qu'une information scientifique conserve une formulation prudente et comprehensible."),
            ],
            culture=[
                _news(date, "Une exposition explore l'art du quotidien", "Culture", "Cette annonce imaginaire rassemble affiches, objets et photographies autour des gestes ordinaires. Elle sert uniquement a tester la place d'une rubrique culturelle dans l'equilibre general du journal."),
            ],
        ),
        tech=[
            DigestItem(title=item.title, summary=item.summary, source=item.source, importance=item.importance)
            for item in tech_news
        ],
        tech_news=tech_news,
        curiosity_news=curiosity_news,
        watch=[
            DigestItem(title="Interfaces vocales locales", summary="L'evolution des interfaces vocales locales et la qualite de leur mode hors ligne."),
            DigestItem(title="Question ouverte", summary="Comment garder une confirmation humaine claire sans ralentir les actions ordinaires ?"),
        ],
        newsletter_digest=[
            DigestItem(title="DEMO - Lettre sur le design calme", summary="Trois principes : moins de signaux, une hierarchie nette et des choix reversibles.", source=_source(date, "newsletter")),
            DigestItem(title="DEMO - Revue de creation", summary="Une selection fictive de methodes pour mieux preparer une idee avant de produire.", source=_source(date, "newsletter")),
        ],
        social_digest=[
            DigestItem(
                title="DEMO - Reseau photo, compte principal",
                summary="Compte fictif : abonnes stables et deux videos en progression depuis la veille.",
            ),
            DigestItem(
                title="DEMO - Reseau photo, compte secondaire",
                summary="Compte fictif : une publication recente et une hausse legere des vues.",
            ),
        ],
        community_digest=[
            DigestItem(
                title="DEMO - Communaute, activite des espaces suivis",
                summary="Donnees fictives : 24 messages, trois salons actifs et une mention en vingt-quatre heures.",
            ),
        ],
        recommendations=[
            Recommendation(title="Une promenade sans ecouteurs", kind="Rituel", reason="Vingt minutes pour laisser retomber le bruit informationnel."),
            Recommendation(title="Relire une page annotee", kind="Lecture", reason="Reprendre une idee deja utile plutot que chercher une nouvelle source."),
        ],
        personal=PersonalBlock(
            greeting="Bonjour. La journee est dense mais bien decoupee.",
            note="Commence par le bloc de 9 h. Le reste peut attendre que cette avance soit prise.",
            free_window="Tu as environ 45 minutes libres entre 13 h 15 et 14 h.",
        ),
        extras=Extras(
            quote=QuoteBlock(text="La clarte vient moins de la quantite que de l'ordre.", author="Formulation de demonstration"),
            word=WordOfTheDay(word="Limpide", definition="Qui se comprend sans effort inutile.", example="Une consigne limpide protege l'attention."),
            stat_of_day=DigestItem(title="3", summary="priorites fortes suffisent pour donner une direction a la journee."),
            quiz=QuizBlock(question="Quel objet mesure le temps sans donner l'heure ?", answer="Un sablier."),
            reflection="Quelle information peux-tu ignorer aujourd'hui sans rien perdre d'important ?",
        ),
        learning=construire_apprentissage_du_jour(date),
        sport=_sport_demo(date, at),
        markets=_markets_demo(),
        editorial=EditorialBlock(
            title="DEMO - L'essentiel du matin",
            text=("Cet édito fictif montre la place du texte rédigé par Claude chaque matin. "
                  "Il relie les trois ou quatre informations majeures du jour et dit ce qu'il faut "
                  "en retenir, sans rien ajouter aux dépêches reçues. Sa longueur est celle d'un "
                  "vrai édito : cinq à six phrases, de quoi poser le contexte et relier les sujets. "
                  "Il est composé sur deux colonnes en bas de la une. Si Claude est indisponible, "
                  "ce bandeau retrouve sa forme habituelle et le journal sort quand même, "
                  "simplement sans texte généré ce matin-là."),
            tech_insight="DEMO - Une lecture courte de la veille tech et IA du jour.",
            markets_insight="DEMO - Une lecture courte des marchés, sans conseil d'investissement.",
            author="demo",
        ),
    )
    return edition
